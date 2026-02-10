
import yaml

from ..models.well_model import WellModel

def yaml_parser(yaml_file: str) -> WellModel:
    """ load a yaml file
        Args:
            yaml_file (str): yaml configuration file

        Returns:
            WellModel: Pydantic model

    """
    # load configuration file
    with open(yaml_file, "r") as f:
        config = yaml.safe_load(f)

    # yaml_config = yaml.dump(config, sort_keys=False)
    # print(yaml_config)

    # dict => pydantic model
    well = WellModel(**config)

    return well
