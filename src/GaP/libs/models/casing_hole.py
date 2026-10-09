from __future__ import annotations

from math import isfinite
from typing import Iterable

from pydantic import BaseModel, Field, field_validator


class CasingHole(BaseModel):
    """One experimental area-equivalent opening on a casing's +X side."""

    casing: str
    depth_mTVDMSL: float = Field(allow_inf_nan=False)
    diameter_m: float = Field(gt=0, allow_inf_nan=False)

    @field_validator("casing")
    @classmethod
    def casing_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("casing hole requires a non-blank casing name")
        return value

    def validate_casing(self, casings: Iterable[tuple[str, float, float]]) -> None:
        matches = [(top, bottom) for name, top, bottom in casings if name == self.casing]
        if len(matches) != 1:
            raise ValueError(f"casing hole must select exactly one casing named {self.casing!r}; found {len(matches)}")
        top, bottom = matches[0]
        if not (isfinite(top) and isfinite(bottom) and top <= self.depth_mTVDMSL < bottom):
            raise ValueError("casing hole depth must lie inside the casing's top-inclusive, bottom-exclusive interval")
