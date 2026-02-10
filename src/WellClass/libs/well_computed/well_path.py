from typing import Callable, Union

import numpy as np
import scipy.interpolate as interp
import wellpathpy as wp

from src.WellClass.libs.models.well_model_utils import WellSurveyModel


def build_wellpath_object(survey: WellSurveyModel, total_depth: Union[float, int], survey_bool: bool) -> wp.position_log:
    """build wellpath object from survey data"""

    if survey_bool:
        survey_td = survey["md_rkb"]
        if total_depth > max(survey_td):
            survey["md_rkb"].append(total_depth)
            survey["inclination_deg"].append(survey["inclination_deg"][-1])
            survey["azimuth_deg"].append(survey["azimuth_deg"][-1])

        deviation = wp.deviation(md=survey["md_rkb"], inc=survey["inclination_deg"], azi=survey["azimuth_deg"])

    else:
        deviation = wp.deviation(md=[0, total_depth], inc=[0, 0], azi=[0, 0])

    pos = deviation.minimum_curvature()

    return pos


def md2tvd_interpolator(pos: wp.position_log, rkb: float) -> Callable[[float], float]:
    """create an interpolator function to convert md to tvd"""

    md = np.asarray(pos.deviation().md)
    tvdmsl = np.asarray(pos.depth) - rkb

    return interp.PchipInterpolator(md, tvdmsl, extrapolate=True)
