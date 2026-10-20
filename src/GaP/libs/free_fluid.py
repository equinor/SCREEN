"""Properties of cells that hold only free fluid: ocean layers, open hole and pipe interior."""

import warnings

FREE_FLUID_PERMX = 10000.0  # mD
FREE_FLUID_PORO = 1.0


def resolve_free_fluid_permx(free_fluid_permx: float | None = None, oh_perm: float | None = None) -> float:
    """Free-fluid permeability in mD; the deprecated open-hole value is accepted only if it agrees."""
    if oh_perm is None:
        return FREE_FLUID_PERMX if free_fluid_permx is None else float(free_fluid_permx)
    warnings.warn(
        "--oh-perm is deprecated; open hole uses the free-fluid permeability (GridPolicy free_fluid_permx or --free-fluid-permx)",
        FutureWarning,
        stacklevel=2,
    )
    if free_fluid_permx is not None and float(oh_perm) != float(free_fluid_permx):
        raise ValueError(
            f"--oh-perm {oh_perm:g} mD conflicts with the free-fluid permeability {free_fluid_permx:g} mD; "
            "set free_fluid_permx in GridPolicy (or --free-fluid-permx) instead"
        )
    return float(oh_perm)
