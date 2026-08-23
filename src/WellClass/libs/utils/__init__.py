
# from .csv_parser import csv_parser
# from .yaml_parser import yaml_parser

def xlsx_to_well_model(*args, **kwargs):
	"""Lazy wrapper to avoid import cycles during WellClass model imports."""

	from .xlsx_parser import xlsx_to_well_model as _xlsx_to_well_model

	return _xlsx_to_well_model(*args, **kwargs)


def xlsx_grid_policy(*args, **kwargs):
	"""Lazy wrapper to avoid import cycles during WellClass model imports."""

	from .xlsx_parser import xlsx_grid_policy as _xlsx_grid_policy

	return _xlsx_grid_policy(*args, **kwargs)


__all__ = ["xlsx_to_well_model", "xlsx_grid_policy"]
