from typing import Callable, Dict, List, Optional


def compute_annulus(
    holes: List[Dict], casings: List[Dict], md2tvd: Callable[[float], float], cement_bond: Optional[List[Dict]], solve_cement_bond: bool = False
) -> List[Dict]:
    holes_casings_merged = holes + casings
    annulus_intervals = []

    # Determine which intervals to process based on solve_cement_bond flag and availability of cement_bond data
    intervals_to_process = cement_bond if solve_cement_bond and cement_bond is not None else casings

    for cb in reversed(intervals_to_process):
        cb_top = cb["top_rkb"]
        cb_bottom = cb["bottom_rkb"]
        cb_id = cb["diameter_m"]
        cb_id_in = cb["diameter_in"]

        holes_larger = [
            item for item in holes_casings_merged if item["diameter_m"] > cb_id and item["bottom_rkb"] > cb_top and item["top_rkb"] < cb_bottom
        ]
        holes_larger_sorted = sorted(holes_larger, key=lambda x: x["diameter_m"])

        cb_remaining_top = cb_top
        cb_remaining_bottom = cb_bottom

        for hl in holes_larger_sorted:
            cb_overlap_top = max(hl["top_rkb"], cb_remaining_top)
            cb_overlap_bottom = min(hl["bottom_rkb"], cb_remaining_bottom)
            cb_overlap_od = hl["diameter_m"]
            cb_overlap_od_in = hl["diameter_in"]

            if cb_overlap_bottom <= cb_overlap_top:
                # no valid overlap,
                continue

            # Shrink remaining interval by removing the overlap just processed
            if cb_overlap_bottom < cb_remaining_bottom:
                cb_remaining_top = cb_overlap_bottom

            if cb_overlap_top > cb_remaining_top:
                cb_remaining_bottom = cb_overlap_top

            # if cb_remaining_length > 0:
            annulus_intervals.append(
                {
                    "top_rkb": cb_overlap_top,
                    "bottom_rkb": cb_overlap_bottom,
                    "top_tvd_msl": md2tvd(cb_overlap_top),
                    "bottom_tvd_msl": md2tvd(cb_overlap_bottom),
                    "id_m": cb_id,
                    "od_m": cb_overlap_od,
                    "id_in": cb_id_in,
                    "od_in": cb_overlap_od_in,
                }
            )

    # Sort intervals by top_rkb ascending, then id_in descending
    annulus_intervals = sorted(annulus_intervals, key=lambda x: (x["top_rkb"], -x["id_in"]))

    return annulus_intervals
