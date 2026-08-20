"""validate input drilling, casing, cement bond, and barriers"""

# def valid_drilling(drilling_df: pd.DataFrame):
#     """ validate drilling input
#     """

#     # ensure it is monotonic decreasing
#     assert drilling_df['diameter_m'].is_monotonic_decreasing, "drilling needs to be sorted"

#     # extract data
#     top_bot = drilling_df.loc[:, ['top_msl', 'bottom_msl']].values
#     top = top_bot[:, 0]
#     bot = top_bot[:, 1]

#     # ensure the depth order is correct
#     assert (top < bot).all()

#     # ensure the bottom depth matches its next top depth
#     assert (top[1:] == bot[:-1]).all()

# def valid_casings(casings_df: pd.DataFrame):
#     """ validate casings input
#     """

#     # ensure it is monotonic decreasing
#     assert casings_df['diameter_m'].is_monotonic_decreasing, "casings needs to be sorted"

#     # extract data
#     columns = ['diameter_m', 'top_msl', 'bottom_msl', 'toc_msl', 'boc_msl']
#     casing_cols = casings_df.loc[:, columns]

#     # ensure the depth order is correct
#     assert (casing_cols['top_msl'].values < casing_cols['bottom_msl'].values).all() #casing intervals
#     assert (casing_cols.dropna()['toc_msl'].values < casing_cols.dropna()['boc_msl'].values).all() #cement bond intervals

#     # in intervals with cement bond, ensure the cement bond is within its corresponding casing
#     assert (casing_cols.dropna()['top_msl'].values <=    casing_cols.dropna()['toc_msl'].values).all()
#     assert (casing_cols.dropna()['bottom_msl'].values >= casing_cols.dropna()['boc_msl'].values).all()


# def valid_barriers(barriers_df: pd.DataFrame):
#     """ validate barriers input
#     """
#     pass


def split_hole_casings(data: list[dict]) -> dict[str, list[dict]]:
    hole = [item for item in data if item["type"] == "hole"]
    casing = [item for item in data if item["type"] == "casing"]
    casing_cement = [item for item in data if item["type"] == "casing cement"]
    return {"holes": hole, "casing": casing, "casing_cement": casing_cement}


def verify_item(data: list[dict], item: str) -> None:
    if not data:
        return

    diameters = [d["diameter_m"] for d in data]
    if not all(diameters[i] >= diameters[i + 1] for i in range(len(diameters) - 1)):
        raise AssertionError(f"{item} list needs to be sorted by diameter_m descending")

    tops = [d["top_rkb"] for d in data]
    bottoms = [d["bottom_rkb"] for d in data]

    # Check top < bottom for all intervals
    if any(t >= b for t, b in zip(tops, bottoms)):
        raise AssertionError(f"Each {item} interval top_rkb must be less than bottom_rkb")

    if item == "holes" and any(bottoms[i] != tops[i + 1] for i in range(len(bottoms) - 1)):
        raise AssertionError(f"Bottom depth must match next top depth in {item} intervals")


def verify_casings_cement(casings: list[dict], cement_bond: list[dict]) -> None:
    casings_sorted = sorted(casings, key=lambda x: x["top_rkb"], reverse=True)
    cement_bond_sorted = sorted(cement_bond, key=lambda x: x["top_rkb"], reverse=True)

    # Ensure that there are at least as many cement bond intervals as casing intervals
    if len(cement_bond_sorted) < len(casings_sorted):
        raise AssertionError("There must be at least as many cement bond intervals as casing intervals")

    for casing in casings:
        casing_top_rkb = casing["top_rkb"]
        casing_bottom_rkb = casing["bottom_rkb"]
        casing_diameter = casing["diameter_in"]

        for cement in cement_bond:
            cement_top_rkb = cement["top_rkb"]
            cement_bottom_rkb = cement["bottom_rkb"]
            cement_diameter = cement["diameter_in"]

            if cement_diameter == casing_diameter:
                if cement_top_rkb < casing_top_rkb:
                    raise AssertionError(
                        f"Top of cement bond interval ({cement_top_rkb:.1f} mRKB) cannot be shallower than top of casing interval ({casing_top_rkb:.1f} mRKB) for diameter {casing_diameter} in"
                    )

                if cement_bottom_rkb > casing_bottom_rkb:
                    raise AssertionError(
                        f"Bottom of cement bond interval ({cement_bottom_rkb:.1f} mRKB) cannot be deeper than bottom of casing interval ({casing_bottom_rkb:.1f} mRKB) for diameter {casing_diameter} in"
                    )


def verify_hole_casings(data: list[dict]) -> None:
    split_hc = split_hole_casings(data)

    verify_casings_cement(split_hc["casing"], split_hc["casing_cement"])

    for item, item_data in split_hc.items():
        if item_data:  # Only verify if there is data for this item
            verify_item(item_data, item)


def verify_plugs(data: list[dict], ground_elevation: float) -> None:
    cement_plugs = [item for item in data if item["type"] == "cement"]

    tops = [d["top_rkb"] for d in data]
    bottoms = [d["bottom_rkb"] for d in data]

    depths = tops + bottoms

    if any(d < ground_elevation for d in depths):
        raise AssertionError(f"Plugs cannot be have depths shallower than ground elevation {ground_elevation:.1f} mTVDMSL")

    for plug in cement_plugs:
        if plug["top_rkb"] >= plug["bottom_rkb"]:
            raise AssertionError(
                f"Cement plug interval top_rkb ({plug['top_rkb']:.1f} mRKB) must be shallower than bottom_rkb ({plug['bottom_rkb']:.1f} mRKB)"
            )


def verify_stratigraphy(data: list[dict], ground_elevation: float) -> None:
    tops = [d["top_rkb"] for d in data]
    bottoms = [d["bottom_rkb"] for d in data]

    # Concatenate tops and bottoms to check all depths against ground elevation
    depths = tops + bottoms
    if any(d < ground_elevation for d in depths):
        raise AssertionError(f"Stratigraphy cannot be have depths shallower than ground elevation {ground_elevation:.1f} mTVDMSL")

    # Check top < bottom for all intervals
    for interval in data:
        if interval["top_rkb"] >= interval["bottom_rkb"]:
            raise AssertionError(
                f"Stratigraphy top_rkb ({interval['top_rkb']:.1f} mRKB) must be shallower than bottom_rkb ({interval['bottom_rkb']:.1f} mRKB)"
            )
