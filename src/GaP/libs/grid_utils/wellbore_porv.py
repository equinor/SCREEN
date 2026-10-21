"""Undo the bottom-layer pore volume multiplier that LGR cells inherit from their parent cell."""

from typing import TextIO

import pandas as pd


def write_wellbore_porv_reset(holes_df: pd.DataFrame, n_layers: int, multiplier: float, stream: TextIO) -> None:
    """Divide PORV by ``multiplier`` on the open-hole cells of the last LGR layer."""
    bottom = holes_df[holes_df["k_max"] + 1 == n_layers]
    if bottom.empty or multiplier == 1:
        return
    stream.write("-- SCREEN: undo the inherited bottom-layer pore volume multiplier on the open-hole cells\nMULTIPLY\n")
    for _, row in bottom.iterrows():
        low, high = int(row["ij_min"]) + 1, int(row["ij_max"]) + 1
        stream.write(f"PORV {1 / multiplier:.10g} {low} {high} {low} {high} {n_layers} {n_layers} /\n")
    stream.write("/\n")
