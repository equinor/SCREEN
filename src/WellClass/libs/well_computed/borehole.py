import itertools
from typing import Callable, Dict, List, Tuple


def compute_borehole(holes: List[Dict], casings: List[Dict], md2tvd: Callable) -> List[Dict]:
    # concatenate holes and casings
    combined = holes + casings

    # Sort by top_rkb ascending, then diameter_m ascending
    combined_sorted = sorted(combined, key=lambda x: (x["top_rkb"], x["diameter_m"]))

    # Group by top_rkb
    borehole_list: List[Tuple[float, float]] = []
    previous_diam = float("inf")

    # Iterate over groups and find minimum diameter for each top_rkb
    for top_rkb, group in itertools.groupby(combined_sorted, key=lambda x: x["top_rkb"]):
        group_list = list(group)
        min_diam = min(item["diameter_m"] for item in group_list)

        if min_diam < previous_diam:
            borehole_list.append((top_rkb, min_diam))
            previous_diam = min_diam

    # Build borehole intervals with top_rkb, bottom_rkb, and diameter_m
    borehole_intervals = []
    for i, (top, diam) in enumerate(borehole_list):
        if i + 1 < len(borehole_list):
            bottom = borehole_list[i + 1][0]
        else:
            # Last bottom_rkb is max bottom_rkb from combined data
            bottom = max(item["bottom_rkb"] for item in combined)

        borehole_intervals.append(
            {
                "top_rkb": top,
                "bottom_rkb": bottom,
                "top_tvd_msl": md2tvd(top).item(),
                "bottom_tvd_msl": md2tvd(bottom).item(),
                "diameter_m": diam,
            }
        )

    return borehole_intervals
