from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy import constants as const
from scipy.integrate import solve_ivp
from scipy.interpolate import RectBivariateSpline

from ..pvt.pvt import get_pvt
from ..utils.compute_intersection import compute_intersection
from .pressure_table import PressureTable


def _integrate_variable_density(
    depth: np.ndarray,
    ground_elevation: float,
    ground_temperature: float,
    geothermal_gradient: float,
    get_rho: callable,
    reference_depth: float,
    reference_pressure: float,
    direction: str,
) -> np.ndarray:
    """Integrate a variable-density fluid column outward from a reference point.

    Uses `solve_ivp` (adaptive Radau stepping) for the same robustness as
    `pvt.get_hydrostatic_P`'s ODE integration, instead of a fixed-step Euler loop.
    Temperature is evaluated analytically at each internal step (not interpolated
    from the table's sampled array), since the solver picks its own z-values.
    Depths on the other side of `reference_depth` are left as NaN.
    """
    pressure = np.full(depth.shape, np.nan)

    if direction == "up":
        indices = np.flatnonzero(depth <= reference_depth)
        order = np.argsort(depth[indices])[::-1]  # from reference_depth upward (descending depth)
    elif direction == "down":
        indices = np.flatnonzero(depth >= reference_depth)
        order = np.argsort(depth[indices])  # from reference_depth downward (ascending depth)
    else:
        raise ValueError(f"direction must be 'up' or 'down', got {direction!r}")

    indices = indices[order]
    if indices.size == 0:
        return pressure

    z_eval = depth[indices]
    if z_eval[-1] == reference_depth:
        # only the reference point itself is in range - nothing to integrate
        pressure[indices] = reference_pressure
        return pressure

    def temperature_at(z: float) -> float:
        return ground_temperature + max(0.0, z - ground_elevation) * (geothermal_gradient / 1000)

    def odesys(z: float, y: np.ndarray) -> list:
        rho = get_rho(y[0], temperature_at(z))[0, 0]
        return [rho * const.g / const.bar]

    solution = solve_ivp(
        odesys,
        [reference_depth, z_eval[-1]],
        [reference_pressure],
        t_eval=z_eval,
        method="Radau",
    )

    pressure[indices] = np.maximum(solution.y[0], const.atm / const.bar)
    return pressure


@dataclass
class PressureScenario:
    """
    A named pressure scenario for a well.

    Reuses the shared `PressureTable` background curves (temperature, hydrostatic
    pressure, Shmin) and adds the scenario-specific curves: `brine_pressure` and
    `fluid_pressure`, plus the scenario's own metadata (p_delta, fluid datum,
    optional store reference, p_MSAD, z_MSAD).

    The fluid curve is normally derived from the fluid-datum pair. When a
    shallower `z_store`/`p_store` pair is supplied, that pair anchors the
    integration and the fluid-datum pressure is derived from the resulting curve.
    Alternatively, `z_MSAD` anchors the fluid curve at Shmin; the datum is then
    found from the resulting fluid curve or evaluated at a supplied datum depth.
    Curve derivation has two modes:
      - `fluid_gradient` given: a simple constant-gradient (bar/m) extrapolation.
      - `fluid_type` given (default "co2"): a full variable-density integration
        using the named fluid's density table from the in-situ PVT collection.
    """

    name: str
    table: PressureTable

    # Fluid contact/datum: at this point brine and fluid pressure are equal.
    z_fluid_datum: Optional[float] = None
    p_fluid_datum: Optional[float] = None

    # Optional project/store reference. In datum/store scenarios the pair anchors
    # integration; in MSAD scenarios z_store is a pressure-query depth and p_store
    # is derived from the MSAD-anchored fluid curve.
    z_store: Optional[float] = None
    p_store: Optional[float] = None

    # Optional input/derived pressure offset: brine - hydrostatic at the datum.
    p_delta: Optional[float] = None

    # Optional integration anchor: p_MSAD is always derived as Shmin(z_MSAD).
    z_MSAD: Optional[float] = None

    # Fluid derivation: a fixed gradient takes precedence over a named PVT fluid
    fluid_type: Optional[str] = "co2"
    fluid_gradient: Optional[float] = None
    pvt_path: Optional[str] = None

    # Computed curves
    brine_pressure: np.ndarray = field(init=False)
    fluid_pressure: np.ndarray = field(init=False)

    # Computed scalar
    p_MSAD: float = field(init=False, default=np.nan)  # Pressure at Minimum Safe Abandonment Depth
    _integration_depth: float = field(init=False)
    _integration_pressure: float = field(init=False)
    _msad_anchored: bool = field(init=False, default=False)

    def __post_init__(self):
        if self.z_MSAD is None:
            self._resolve_datum_and_store()
        else:
            self._resolve_from_msad()
        self.fluid_pressure = self._compute_fluid_pressure()

        if self._msad_anchored:
            self._resolve_datum_from_msad_curve()
        elif self.p_fluid_datum is None:
            self.p_fluid_datum = float(np.interp(self.z_fluid_datum, self.table.depth, self.fluid_pressure))
            hydrostatic_at_datum = float(np.interp(self.z_fluid_datum, self.table.depth, self.table.hydrostatic_pressure))
            self.p_delta = self.p_fluid_datum - hydrostatic_at_datum

        self.brine_pressure = self.table.hydrostatic_pressure + self.p_delta
        if not self._msad_anchored:
            self.z_MSAD, self.p_MSAD = compute_intersection(self.table.depth, self.table.min_horizontal_stress, self.fluid_pressure)

    def _resolve_from_msad(self) -> None:
        """Use Shmin at z_MSAD as the fluid-curve integration anchor."""
        if self.p_fluid_datum is not None or self.p_delta is not None or self.p_store is not None:
            raise ValueError("z_MSAD cannot be combined with p_fluid_datum, p_delta, or p_store")

        self._validate_depth("z_MSAD", self.z_MSAD)
        if self.z_fluid_datum is not None:
            self._validate_depth("z_fluid_datum", self.z_fluid_datum)
        if self.z_store is not None:
            self._validate_depth("z_store", self.z_store)
            if self.z_fluid_datum is not None and self.z_store > self.z_fluid_datum:
                raise ValueError("z_store cannot be deeper than z_fluid_datum")

        self.p_MSAD = float(np.interp(self.z_MSAD, self.table.depth, self.table.min_horizontal_stress))
        self._integration_depth = self.z_MSAD
        self._integration_pressure = self.p_MSAD
        self._msad_anchored = True

    def _resolve_datum_from_msad_curve(self) -> None:
        """Resolve the contact and brine offset after MSAD-anchored integration."""
        if self.z_fluid_datum is None:
            if self.z_store is not None:
                self.z_fluid_datum = self.z_store
                self.p_fluid_datum = float(np.interp(self.z_fluid_datum, self.table.depth, self.fluid_pressure))
                hydrostatic_at_datum = float(np.interp(self.z_fluid_datum, self.table.depth, self.table.hydrostatic_pressure))
                self.p_delta = self.p_fluid_datum - hydrostatic_at_datum
            else:
                z_datum, p_datum = compute_intersection(self.table.depth, self.fluid_pressure, self.table.hydrostatic_pressure)
                if not np.isfinite(z_datum):
                    raise ValueError("MSAD-anchored fluid curve does not cross hydrostatic pressure within the PressureTable range")
                self._validate_depth("derived z_fluid_datum", z_datum)
                self.z_fluid_datum = z_datum
                self.p_fluid_datum = p_datum
                self.p_delta = 0.0
        else:
            self.p_fluid_datum = float(np.interp(self.z_fluid_datum, self.table.depth, self.fluid_pressure))
            hydrostatic_at_datum = float(np.interp(self.z_fluid_datum, self.table.depth, self.table.hydrostatic_pressure))
            self.p_delta = self.p_fluid_datum - hydrostatic_at_datum

        if self.z_store is None:
            self.z_store = self.z_fluid_datum
        self.p_store = float(np.interp(self.z_store, self.table.depth, self.fluid_pressure))

    def _resolve_datum_and_store(self) -> None:
        """Resolve the fluid datum and select the curve-integration anchor."""
        store_values = (self.z_store, self.p_store)
        if any(value is not None for value in store_values):
            if not all(value is not None for value in store_values):
                raise ValueError("z_store and p_store must be provided together")

        if self.z_fluid_datum is None:
            if self.z_store is None:
                raise ValueError("z_fluid_datum or a complete z_store/p_store pair is required")
            if self.p_delta is not None:
                raise ValueError("p_delta cannot be combined with a store-only reference")
            self.z_fluid_datum = self.z_store
            self.p_fluid_datum = self.p_store

        self._validate_depth("z_fluid_datum", self.z_fluid_datum)

        hydrostatic_at_datum = float(np.interp(self.z_fluid_datum, self.table.depth, self.table.hydrostatic_pressure))

        if self.z_store is None:
            if self.p_fluid_datum is not None and self.p_delta is not None:
                raise ValueError("Provide either p_fluid_datum or p_delta, not both")
            if self.p_fluid_datum is None:
                self.p_delta = 0.0 if self.p_delta is None else self.p_delta
                self.p_fluid_datum = hydrostatic_at_datum + self.p_delta
            else:
                self.p_delta = self.p_fluid_datum - hydrostatic_at_datum

            self.z_store = self.z_fluid_datum
            self.p_store = self.p_fluid_datum
        else:
            self._validate_depth("z_store", self.z_store)
            if self.z_store > self.z_fluid_datum:
                raise ValueError("z_store cannot be deeper than z_fluid_datum")
            if self.p_delta is not None:
                raise ValueError("p_delta cannot be combined with a distinct z_store/p_store integration anchor")
            if self.p_fluid_datum is not None and self.z_store != self.z_fluid_datum:
                raise ValueError("Provide either p_fluid_datum or a distinct z_store/p_store integration anchor, not both")
            if self.p_fluid_datum is not None:
                self.p_delta = self.p_fluid_datum - hydrostatic_at_datum

            self._integration_depth = self.z_store
            self._integration_pressure = self.p_store
            return

        self._integration_depth = self.z_fluid_datum
        self._integration_pressure = self.p_fluid_datum

    def _validate_depth(self, name: str, depth: float) -> None:
        if depth <= self.table.ground_elevation:
            raise ValueError(f"{name} must be deeper than ground_elevation")
        if depth < self.table.depth[0] or depth > self.table.depth[-1]:
            raise ValueError(f"{name} must be within the PressureTable depth range")

    def display_curves(self) -> dict[str, np.ndarray]:
        """Return full brine and the physical visual segment of the fluid curve.

        Brine remains visible across the full PressureTable depth range. Fluid is
        shown only from MSAD to the fluid datum. The full computed arrays remain
        unchanged for calculations. Exact MSAD and datum rows are interpolated
        into the fluid segment when the table grid does not contain those depths,
        preventing gaps at the displayed endpoints.
        """
        if not np.isfinite(self.z_MSAD) or self.z_fluid_datum is None:
            raise ValueError("MSAD and fluid datum must be resolved before display curves can be created")
        if self.z_MSAD > self.z_fluid_datum:
            raise ValueError("z_MSAD must be shallower than or equal to z_fluid_datum for display")

        depth = self.table.depth
        interior = (depth > self.z_MSAD) & (depth < self.z_fluid_datum)
        fluid_depth = np.concatenate(([self.z_MSAD], depth[interior], [self.z_fluid_datum]))

        return {
            "brine_depth": depth.copy(),
            "brine_pressure": self.brine_pressure.copy(),
            "fluid_depth": fluid_depth,
            "fluid_pressure": np.interp(fluid_depth, depth, self.fluid_pressure),
        }

    def _compute_fluid_pressure(self) -> np.ndarray:
        p0 = self._integration_pressure
        z0 = self._integration_depth

        if self.fluid_gradient is not None:
            return p0 + self.fluid_gradient * (self.table.depth - z0)

        get_rho = self._fluid_density_interpolator()
        table = self.table
        upper = _integrate_variable_density(
            table.depth, table.ground_elevation, table.ground_temperature, table.geothermal_gradient, get_rho, z0, p0, "up"
        )
        lower = _integrate_variable_density(
            table.depth, table.ground_elevation, table.ground_temperature, table.geothermal_gradient, get_rho, z0, p0, "down"
        )
        return np.where(table.depth <= z0, upper, lower)

    def _fluid_density_interpolator(self) -> RectBivariateSpline:
        if self.fluid_type != "co2":
            raise ValueError(f"Only 'co2' is available in the in-situ PVT collection right now, got {self.fluid_type!r}")
        if self.pvt_path is None:
            raise ValueError("pvt_path is required to look up a named fluid's density table")

        temperatures, pressures, rho_co2, _ = get_pvt(self.pvt_path)
        return RectBivariateSpline(pressures, temperatures, rho_co2)

    def __repr__(self) -> str:
        return (
            f"PressureScenario({self.name!r}): "
            f"p_fluid_datum={self.p_fluid_datum:.2f} bar @ z_fluid_datum={self.z_fluid_datum:.1f} mTVDMSL, "
            f"p_delta={self.p_delta:+.2f} bar, "
            f"p_store={self.p_store:.2f} bar @ z_store={self.z_store:.1f} mTVDMSL, "
            f"MSAD: p={self.p_MSAD:.2f} bar @ z={self.z_MSAD:.1f} mTVDMSL"
        )
