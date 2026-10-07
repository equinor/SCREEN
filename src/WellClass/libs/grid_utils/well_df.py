from collections.abc import Mapping

import numpy as np
import pandas as pd


class WellDataFrame:
    def __init__(
        self,
        my_well,
        *,
        oh_perm=None,
        cb_perm=None,
        barrier_perm=None,
        permeability_unit="mD",
        permeability_overrides=None,
        interval_permeability_overrides: Mapping[str, Mapping[str, float]] | None = None,
    ):
        """Expose canonical/legacy GaP frames; processed depths are TVDMSL m and permeability is mD."""

        if permeability_unit != "mD":
            raise ValueError("permeability_unit must be 'mD'")
        if hasattr(my_well, "drilling"):
            self._from_legacy_well(my_well)
        elif hasattr(my_well, "hole_casings"):
            self._from_processed_well(
                my_well,
                oh_perm,
                cb_perm,
                barrier_perm,
                permeability_overrides or {},
                interval_permeability_overrides or {},
            )
        else:
            raise TypeError("WellDataFrame requires a legacy Well or WellProcessed instance")

    def _from_legacy_well(self, my_well):
        """Build the original GaP-facing frames from the legacy Well API."""

        # # Dataframes for drilling, casings, borehole and geological tops

        self.drilling_df = pd.DataFrame(my_well.drilling)
        self.casings_df = pd.DataFrame(my_well.casings)
        self.borehole_df = pd.DataFrame(my_well.borehole)
        self.annulus_df = pd.DataFrame(my_well.annulus)
        self.geology_df = pd.DataFrame(my_well.geology)

        # and for the barriers
        self.barriers_df = pd.DataFrame(my_well.barriers)
        self.barriers_mod_df = pd.DataFrame(my_well.barriers_mod)
        self._set_canonical_aliases()

    def _from_processed_well(
        self,
        my_well,
        oh_perm,
        cb_perm,
        barrier_perm,
        permeability_overrides,
        interval_permeability_overrides,
    ):
        """Adapt WellProcessed records to the fields consumed by GaP."""
        if not hasattr(my_well, "borehole") or not hasattr(my_well, "annulus"):
            raise TypeError("WellDataFrame requires a processed well with derived geometry")
        unknown_overrides = set(permeability_overrides) - {"oh_perm", "cb_perm", "barrier_perm"}
        if unknown_overrides:
            raise ValueError(f"unknown permeability overrides: {sorted(unknown_overrides)}")
        unknown_interval_fields = set(interval_permeability_overrides) - {"cb_perm", "barrier_perm"}
        if unknown_interval_fields:
            raise ValueError(f"unknown interval permeability overrides: {sorted(unknown_interval_fields)}")

        records = my_well.hole_casings or []
        holes = [record for record in records if record["type"] == "hole"]
        casings = [record for record in records if record["type"] == "casing"]
        casing_cement = [record for record in records if record["type"] == "casing cement"]

        self.drilling_df = self._interval_frame(
            holes,
            diameter_field="diameter_m",
            permeability_field="hc_perm",
            default_permeability=oh_perm,
        ).rename(columns={"tvd_msl_top": "top_msl", "tvd_msl_bottom": "bottom_msl"})
        if "oh_perm" in permeability_overrides:
            self.drilling_df["hc_perm"] = permeability_overrides["oh_perm"]
        self.drilling_df["oh_perm"] = self.drilling_df["hc_perm"]
        self._require_permeability(self.drilling_df, "oh_perm", "oh_perm")

        casing_frame = self._interval_frame(casings, diameter_field="diameter_m")
        cement_frame = self._interval_frame(casing_cement, diameter_field="diameter_m")
        casing_rows = []
        for _, casing in casing_frame.iterrows():
            matching_cement = cement_frame[
                (cement_frame["diameter_in"] == casing["diameter_in"])
                & (cement_frame["top_rkb"] < casing["bottom_rkb"])
                & (cement_frame["bottom_rkb"] > casing["top_rkb"])
            ]
            cement_row = matching_cement.iloc[0] if not matching_cement.empty else None
            casing_rows.append(
                {
                    **casing.to_dict(),
                    "top_msl": casing["tvd_msl_top"],
                    "bottom_msl": casing["tvd_msl_bottom"],
                    "toc_msl": cement_row["tvd_msl_top"] if cement_row is not None else casing["tvd_msl_top"],
                    "boc_msl": cement_row["tvd_msl_bottom"] if cement_row is not None else casing["tvd_msl_bottom"],
                    "cement_name": cement_row["name"] if cement_row is not None else None,
                    "cb_perm": (cement_row.get("hc_perm") if cement_row is not None and cement_row.get("hc_perm") is not None else cb_perm),
                }
            )
        self.casings_df = pd.DataFrame(casing_rows)
        if "cb_perm" in permeability_overrides:
            self.casings_df["cb_perm"] = permeability_overrides["cb_perm"]
        self._apply_interval_permeability_overrides(
            self.casings_df,
            "cement_name",
            "cb_perm",
            interval_permeability_overrides.get("cb_perm", {}),
            "casing-cement",
        )
        self._require_permeability(self.casings_df, "cb_perm", "cb_perm")

        self.borehole_df = pd.DataFrame(my_well.borehole)
        if not self.borehole_df.empty:
            self.borehole_df["top_msl"] = self.borehole_df["top_tvd_msl"]
            self.borehole_df["bottom_msl"] = self.borehole_df["bottom_tvd_msl"]

        self.annulus_df = pd.DataFrame(my_well.annulus)
        if not self.annulus_df.empty:
            self.annulus_df["top_msl"] = self.annulus_df["top_tvd_msl"]
            self.annulus_df["bottom_msl"] = self.annulus_df["bottom_tvd_msl"]
            self.annulus_df["thick_m"] = self.annulus_df["an_thickness_m"]

        self.geology_df = pd.DataFrame(my_well.stratigraphy or [])
        self.barriers_df = pd.DataFrame(my_well.plugs or [])
        self.barriers_mod_df = self._processed_barriers(my_well, barrier_perm)
        if "barrier_perm" in permeability_overrides:
            self.barriers_mod_df["barrier_perm"] = permeability_overrides["barrier_perm"]
        self._apply_interval_permeability_overrides(
            self.barriers_mod_df,
            "barrier_name",
            "barrier_perm",
            interval_permeability_overrides.get("barrier_perm", {}),
            "plug",
        )
        self._require_permeability(self.barriers_mod_df, "barrier_perm", "barrier_perm")
        self._set_canonical_aliases()

    @staticmethod
    def _apply_interval_permeability_overrides(frame, identifier_column, value_column, overrides, interval_type):
        for identifier, value in overrides.items():
            if not isinstance(identifier, str) or not identifier.strip() or identifier == "ALL":
                raise ValueError(f"invalid {interval_type} interval identifier: {identifier!r}")
            try:
                numeric_value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{value_column} override for {identifier!r} must be finite and nonnegative in mD"
                ) from exc
            if not np.isfinite(numeric_value) or numeric_value < 0:
                raise ValueError(f"{value_column} override for {identifier!r} must be finite and nonnegative in mD")
            matches = frame[identifier_column] == identifier if identifier_column in frame else pd.Series(dtype=bool)
            match_count = int(matches.sum())
            if match_count == 0:
                available = sorted(frame[identifier_column].dropna().unique().tolist()) if identifier_column in frame else []
                raise ValueError(f"unknown {interval_type} interval {identifier!r}; available intervals: {available}")
            if match_count > 1:
                raise ValueError(f"ambiguous {interval_type} interval {identifier!r}; names must be unique")
            frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce").astype(float)
            frame.loc[matches, value_column] = numeric_value

    def _set_canonical_aliases(self):
        self.holes_df = self.drilling_df
        self.plugs_df = self.barriers_df
        self.barrier_regions_df = self.barriers_mod_df

    @staticmethod
    def _interval_frame(records, diameter_field=None, permeability_field=None, default_permeability=None):
        frame = pd.DataFrame(records)
        if frame.empty:
            return frame
        if diameter_field and diameter_field not in frame:
            frame[diameter_field] = frame["diameter_in"] * 0.0254
        if permeability_field:
            if permeability_field not in frame:
                frame[permeability_field] = default_permeability
            else:
                frame[permeability_field] = frame[permeability_field].fillna(default_permeability)
        return frame

    @staticmethod
    def _require_permeability(frame, field, parameter_name):
        if frame.empty:
            return
        values = pd.to_numeric(frame[field], errors="coerce")
        if values.isna().any():
            raise ValueError(f"{parameter_name} must be provided for processed wells")
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError(f"{parameter_name} must be finite and nonnegative in mD")
        frame[field] = values

    @staticmethod
    def _processed_barriers(my_well, barrier_perm):
        records = []
        for plug in my_well.processed_plugs or []:
            permeability = plug.get("cement_perm")
            if permeability is None:
                permeability = barrier_perm
            records.append(
                {
                    "barrier_name": plug["name"],
                    "top_msl": plug["top_tvd_msl"],
                    "bottom_msl": plug["bottom_tvd_msl"],
                    "diameter_m": plug["diameter_m"],
                    "barrier_perm": permeability,
                }
            )
        frame = pd.DataFrame(
            records,
            columns=["barrier_name", "top_msl", "bottom_msl", "diameter_m", "barrier_perm"],
        )
        WellDataFrame._require_permeability(frame, "barrier_perm", "barrier_perm")
        return frame
