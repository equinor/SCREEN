import numpy as np


def compute_intersection(x: np.ndarray, y1: np.ndarray, y2: np.ndarray):
    """Return the first linear intersection of two sampled curves.

    NaN values in either curve are ignored. If no crossing exists, the
    function returns ``(nan, nan)``.
    """
    x = np.asarray(x, dtype=float)
    y1 = np.asarray(y1, dtype=float)
    y2 = np.asarray(y2, dtype=float)

    if not (x.shape == y1.shape == y2.shape):
        raise ValueError("x, y1, and y2 must have the same shape")

    valid = np.isfinite(x) & np.isfinite(y1) & np.isfinite(y2)
    x = x[valid]
    y1 = y1[valid]
    y2 = y2[valid]
    difference = y1 - y2

    for index in range(len(x) - 1):
        left_difference = difference[index]
        right_difference = difference[index + 1]

        if left_difference == 0:
            return x[index], y1[index]
        if left_difference * right_difference > 0:
            continue
        if right_difference == 0:
            return x[index + 1], y1[index + 1]

        fraction = -left_difference / (right_difference - left_difference)
        intersect_x = x[index] + fraction * (x[index + 1] - x[index])
        intersect_y = y1[index] + fraction * (y1[index + 1] - y1[index])
        return intersect_x, intersect_y

    return np.nan, np.nan
