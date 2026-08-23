from typing import Dict, List, Optional, Tuple

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
from matplotlib.patches import Rectangle

from ..utils.fraction_float import float_to_fraction_inches
from ..well_class.well_class import Well

ZONATION_COLORS = {
    "reservoir": "#f6d55c",
    "flow_unit": "#f4a261",
    "barrier": "#1b5e20",
}


def split_hole_casings(data: list[dict]) -> dict[str, list[dict]]:
    hole = [item for item in data if item["type"] == "hole"]
    casing = [item for item in data if item["type"] == "casing"]
    casing_cement = [item for item in data if item["type"] == "casing cement"]
    return {"holes": hole, "casing": casing, "casing_cement": casing_cement}


def hole_plotter(ax: matplotlib.axes.Axes, data: List[Dict], hole_bool: bool, fill_bool: bool = True, z_order: int = 0) -> None:
    """
    Draws all open hole elements. Applies for both drilling and borehole dataframes
    """

    if hole_bool:
        for row in data:
            top = row.get("top_tvd_msl", row.get("tvd_msl_top"))
            bottom = row.get("bottom_tvd_msl", row.get("tvd_msl_bottom"))
            if top is None or bottom is None:
                raise KeyError("Hole records require top and bottom TVD MSL fields")

            xy = (-row["diameter_m"] / 2, top)
            width = row["diameter_m"]
            height = bottom - top
            ax.add_patch(Rectangle(xy, width, height, zorder=z_order, fill=fill_bool, facecolor=r"#CB8A58"))


def casings_plotter(
    ax: matplotlib.axes.Axes,
    data: List[Dict],
    color_tone: str,
    txt_size: int,
    x_txt_pos: float,
    annot_bool: bool,
    casings_bool: bool,
    c_shoe_bool: bool,
    c_weld_bool: bool,
) -> None:
    """
    Draws all components linked to the tubular assembly:
    - Casings
    - Casing shoes/welded transitions
    - Annotations
    """

    y_base = [item["tvd_msl_bottom"] for item in data]
    y_top = [item["tvd_msl_top"] for item in data]
    x_left = [-item["diameter_m"] / 2 for item in data]
    x_right = [item["diameter_m"] / 2 for item in data]
    shoe_size = 3

    # Create marker for casing shoe
    left_shoe = [[0, 0], [-shoe_size, 0], [0, shoe_size], [0, 0]]
    right_shoe = [[0, 0], [shoe_size, 0], [0, shoe_size], [0, 0]]

    # query dataframe for shoe items
    shoe_items = [item for item in data if item.get("shoe", False)]

    # define x and y positions
    y_pos_shoe = [item["tvd_msl_bottom"] for item in shoe_items]
    right_x_pos_shoe = [item["diameter_m"] / 2 for item in shoe_items]
    left_x_pos_shoe = [-item["diameter_m"] / 2 for item in shoe_items]

    # query dataframe for welded sections
    weld_items = [item for item in data if not item.get("shoe", False)]

    # Draw casings
    if casings_bool:
        for x_l, x_r, y_t, y_b in zip(x_left, x_right, y_top, y_base):
            # draw right hand casing
            ax.vlines(x=x_right, ymin=y_top, ymax=y_base, color=color_tone, lw=1.5, zorder=10)

            # draw left hand casing
            ax.vlines(x=x_left, ymin=y_top, ymax=y_base, color=color_tone, lw=1.5, zorder=10)

    # Draw casing shoes
    if c_shoe_bool:
        # draw left casing shoe
        ax.scatter(left_x_pos_shoe, y_pos_shoe, marker=left_shoe, c=color_tone, zorder=10)

        # draw right casing shoe
        ax.scatter(right_x_pos_shoe, y_pos_shoe, marker=right_shoe, c=color_tone, zorder=10)

    # Draw welded
    if c_weld_bool:
        for item in weld_items:
            max_D = item["diameter_m"]
            max_Z = item["tvd_msl_bottom"]

            candidates = [c for c in data if c["diameter_m"] < max_D and c["tvd_msl_top"] == max_Z]
            if not candidates:
                continue

            min_D = min(c["diameter_m"] for c in candidates)

            ax.plot([max_D / 2, min_D / 2], [max_Z] * 2, c=color_tone, zorder=10)
            ax.plot([-max_D / 2, -min_D / 2], [max_Z] * 2, c=color_tone, zorder=10)

    # Draw annotations (only meaningful if the shoes they label are actually drawn)
    if annot_bool and c_shoe_bool:
        for item in shoe_items:
            ycoord = item["tvd_msl_bottom"]
            d_in = item["diameter_in"]
            shoe_label = float_to_fraction_inches(d_in) + " shoe"

            ax.annotate(shoe_label, xy=(x_txt_pos, ycoord), fontsize=txt_size, va="center", ha="right", clip_on=True)


def cement_bond_plotter(ax: matplotlib.axes.Axes, data: List[Dict], cement_bond_bool: bool) -> None:
    if cement_bond_bool:
        for row in data:
            width = (row["od_m"] - row["id_m"]) / 2
            height = row["bottom_tvd_msl"] - row["top_tvd_msl"]

            right_xy = (row["id_m"] / 2, row["top_tvd_msl"])
            left_xy = (-row["od_m"] / 2, row["top_tvd_msl"])

            ax.add_patch(Rectangle(right_xy, width, height, facecolor="lightgray", zorder=5, hatch="\\\\\\"))
            ax.add_patch(Rectangle(left_xy, width, height, facecolor="lightgray", zorder=5, hatch="///"))


def cement_plug_plotter(
    ax: matplotlib.axes.Axes, plugs: List[Dict], processed_plugs: List[Dict], plug_bool: bool, annot_bool: bool, txt_size: int
) -> None:
    """
    axis: Matplotlib object where items will be plotted
    df_barriers: Dataframe listing the barriers
    df_barriers_mod: Dataframe that describes the visual display of barriers.
    plug_bool: Boolean if barriers are to be displayed
    annot_bool: Boolean if annotations are to be included

    """

    if plug_bool:
        for row in processed_plugs:
            xy = (-row["diameter_m"] / 2, row["top_tvd_msl"])
            width = row["diameter_m"]
            height = row["bottom_tvd_msl"] - row["top_tvd_msl"]
            ax.add_patch(Rectangle(xy, width, height, facecolor="gray", zorder=1))

    # Plug labels are only meaningful once the plugs themselves are drawn
    if annot_bool and plug_bool:
        for row in plugs:
            ycoord = (row["tvd_msl_top"] + row["tvd_msl_bottom"]) / 2
            ax.annotate(text=row["name"], xy=(0, ycoord), fontsize=txt_size, va="center", ha="center", clip_on=True)


def stratigraphy_plotter(
    ax: matplotlib.axes.Axes, data: List[Dict], w_header: Dict, geol_bool: bool, annot_bool: bool, width: float, x_txt_pos: float, txt_size: int
) -> None:
    tops_hlines = [item["tvd_msl_top"] for item in data]

    if geol_bool:
        ax.hlines(y=tops_hlines, xmin=-width, xmax=width, zorder=-4, lw=0.25, color="k")
        ax.axhspan(0, w_header["ground_elevation"], color="lightblue", alpha=0.5, zorder=-20)
        ax.axhspan(w_header["ground_elevation"], w_header["total_depth_rkb"], color="tan", alpha=0.5, zorder=-20)

        for row in data:
            color = ZONATION_COLORS.get(row.get("unit_type"))
            if color:
                ax.axhspan(row["tvd_msl_top"], row["tvd_msl_bottom"], color=color, alpha=0.35, zorder=-10)

    # Geology labels are only meaningful once the geology bands are drawn
    if annot_bool and geol_bool:
        for row in data:
            ycoord = (row["tvd_msl_top"] + row["tvd_msl_bottom"]) / 2
            ax.annotate(text=row["name"], xy=(x_txt_pos, ycoord), fontsize=txt_size, va="center", clip_on=True)


def plot_sketch(
    mywell: Well,
    ax: Optional[matplotlib.axes.Axes] = None,
    *,
    save_file: Optional[str] = None,
    **kwargs,
) -> Tuple[matplotlib.figure.Figure, matplotlib.axes.Axes]:
    """
    plot well sketch

    """

    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.figure

    # Automatically define the y scale in 250 m intervals
    loc = plticker.MultipleLocator(base=250)  # this locator puts ticks at regular intervals
    ax.yaxis.set_major_locator(loc)

    hole_casings = split_hole_casings(mywell.hole_casings)

    hole_data = hole_casings["holes"]
    casing_data = hole_casings["casing"]
    cement_bond = mywell.cement_bond
    borehole_data = mywell.borehole
    plugs_data = mywell.plugs
    processed_plugs_data = mywell.processed_plugs
    stratigraphy_data = mywell.stratigraphy

    # define plot spatial references
    max_diameter = max([item["diameter_m"] for item in hole_data])
    AX_WIDTH = max_diameter  # plot width
    XCOORD_LEFT = -max_diameter / 2  # well construction text
    XCOORD_RIGHT = max_diameter / 2  # geology text
    TXT_FS_LEFT = 7
    TXT_FS_RIGHT = 6
    STEELCOLOR = "#702F00"
    # base_deepest_rsrv = stratigraphy_data[stratigraphy_data.reservoir_flag]["base_msl"].max()
    ymax = max([item["tvd_msl_bottom"] for item in stratigraphy_data])

    # Draw drilling (Bit size)
    hole_plotter(ax, hole_data, kwargs.get("draw_hole", True))

    # draw_annotation is the shared default; draw_casing_annotation/draw_plug_annotation/
    # draw_geology_annotation let callers override each label group independently.
    draw_annotation = kwargs.get("draw_annotation", True)

    # Draw casings
    casings_plotter(
        ax=ax,
        data=casing_data,
        color_tone=STEELCOLOR,
        txt_size=TXT_FS_LEFT,
        x_txt_pos=XCOORD_LEFT,
        annot_bool=kwargs.get("draw_casing_annotation", draw_annotation),
        casings_bool=kwargs.get("draw_casings", True),
        c_shoe_bool=kwargs.get("draw_casing_shoes", True),
        c_weld_bool=kwargs.get("draw_welded", True),
    )

    # Draw cement bond
    cement_bond_plotter(ax, cement_bond, kwargs.get("draw_cement_bond", True))

    # draw barriers
    cement_plug_plotter(
        ax, plugs_data, processed_plugs_data, kwargs.get("draw_barriers", True), kwargs.get("draw_plug_annotation", draw_annotation), TXT_FS_LEFT
    )

    # Draw open hole (borehole/pipe) for testing only
    hole_plotter(ax, borehole_data, kwargs.get("draw_open_hole", False), fill_bool=False, z_order=100)

    # Draw geological information
    stratigraphy_plotter(
        ax,
        stratigraphy_data,
        mywell.header,
        kwargs.get("draw_geology", True),
        kwargs.get("draw_geology_annotation", draw_annotation),
        AX_WIDTH,
        XCOORD_RIGHT,
        TXT_FS_RIGHT,
    )

    ax.set_xlim(-AX_WIDTH, AX_WIDTH)
    ax.set_ylim(0, ymax)
    ax.invert_yaxis()
    ax.set_ylabel("depth [mMSL]")
    ax.set_xlabel("radius [m]")

    # save figure to the disk
    if save_file:
        fig.savefig(save_file)

    return fig, ax
