from typing import Any, Dict, List


def compute_plug_properties(processed_plugs: List[Dict[str, Any]], plug_names: List[str], eval_plug: str) -> Dict[str, Any]:
    if eval_plug not in plug_names:
        raise ValueError(f"Plug name '{eval_plug}' not found in plug_names list.")

    matching_items = [plug for plug in processed_plugs if plug.get("name") == eval_plug]

    if not matching_items:
        raise ValueError(f"No plugs found with name '{eval_plug}'")

    matching_items = sorted(matching_items, key=lambda x: x["top_rkb"])

    top_rkb = matching_items[0]["top_rkb"]
    bottom_rkb = matching_items[-1]["bottom_rkb"]
    top_tvd_msl = matching_items[0]["top_tvd_msl"]
    bottom_tvd_msl = matching_items[-1]["bottom_tvd_msl"]

    thickness_tvd = bottom_tvd_msl - top_tvd_msl
    thickness_md = bottom_rkb - top_rkb

    if thickness_md == 0:
        raise ValueError(f"Plug '{eval_plug}' has zero thickness in measured depth")

    avg_diam = 0.0

    for item in matching_items:
        segment_thickness_md = item["bottom_rkb"] - item["top_rkb"]
        segment_diameter = item["diameter_m"]

        avg_diam += segment_diameter * segment_thickness_md

    avg_diam /= thickness_md
    plug_radius = avg_diam / 2.0

    return {
        "name": eval_plug,
        "top_rkb": top_rkb,
        "bottom_rkb": bottom_rkb,
        "top_tvd_msl": float(top_tvd_msl),
        "bottom_tvd_msl": float(bottom_tvd_msl),
        "thickness_tvd": float(thickness_tvd),
        "thickness_md": float(thickness_md),
        "radius": plug_radius,
    }
