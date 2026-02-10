"""
How to initialize:

```
import well_class

INDATA          = <path to a csv-file with the well-data>

#Reads the csv-file and organize the data into a dict of dataframes

well_df         = well_class.csv_parser(INDATA)
```

Then the class is initialized with a lot of explicit calls. (Bad structure - should been done in one go: ```mywell = Well(INDATA)```)

```
mywell          = well_class.Well(
                       header       = well_df['well_header'],
                       reservoir_P  = well_df['reservoir_pressure'],
                       drilling     = well_df['drilling'],
                       casings      = well_df['casing_cement'],
                       barriers     = well_df['barriers'],
                       geology      = well_df['geology'],
                       main_barrier = well_df['main_barrier'],
                       barrier_perm = well_df['barrier_permeability'],
                       co2_datum    = well_df['co2_datum']
                   )
```

Now additional functionalities that can be explicitely called are
```
   .plot_pt()

   .plot_pressure()  + plt.show()

   .plot_sketch()    + plt.show()
```

"""

# handle type hints problem for python version < 3.10
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class WellRaw:
    """
    Basic user input well information
    Args:
    header (dict): well header
    hole_casings (list of dict): list of hole and casing information
    survey (dict of list): survey information
    plugs (list of dict): list of plug information
    stratigraphy (list of dict): list of stratigraphy information
    """

    header: Optional[Dict[str, Any]] = None
    hole_casings: Optional[List[Dict[str, Any]]] = None
    survey: Optional[Dict[str, List[float]]] = None
    plugs: Optional[List[Dict[str, Any]]] = None
    stratigraphy: Optional[List[Dict[str, Any]]] = None


# @dataclass              # @dataclass(kw_only=True)
# class WellRaw:
#     """ Basic user input well information

#         Args:
#             header (dict): well header
#             drilling (dict): drilling well
#             casings (dict): well casing
#             barriers (dict): barrier information
#             barrier_perm (dict): barrier permeabilities
#             geology (dict): gelogical formation
#             co2_datum (float): co2 datum value
#     """
#     header        : dict = None
#     drilling      : dict = None
#     casings       : dict = None
#     barriers      : dict = None
#     barrier_perm  : dict = None
#     geology       : dict = None
#     co2_datum     : Union[float, int] = None
#     inventory     : dict = None

#     def __post_init__(self):
#         """ compute basic well information
#         """
#         self._check_inventory()
#         self._process_drilling()
#         self._process_casings()
#         self._process_barriers()
#         self._process_geology()

#     def _check_inventory(self):

#         """
#         process to keep track of what has been declared as input.
#         """
#         self.inventory = dict()

#         self.inventory['drilling'] = True
#         self.inventory['casings']  = True
#         self.inventory['barriers'] = True

#         if self.drilling == None:
#             print('No drilling table declared.')
#             """
#             If no drilling table is declared, ignore the casings table as well
#             """
#             self.inventory['drilling'] = False
#             self.inventory['casings'] = False

#         if self.casings == None:
#             print('No casings table declared.')
#             self.inventory['casings'] = False

#         if self.barriers == None:
#             print('No barriers table declared.')
#             self.inventory['barriers'] = False


#     def _process_drilling(self):

#         if not self.inventory['drilling']:
#             """
#             If no drilling table is declared, create a dummy well with info from the header
#             """
#             _well_rkb = self.header['well_rkb']
#             _well_td_rkb = self.header['well_td_rkb']
#             _sf_depth_msl = self.header['sf_depth_msl']

#             self.drilling = [{'top_rkb': _sf_depth_msl + _well_rkb, 'bottom_rkb': _well_td_rkb, 'diameter_in': 17.5, 'oh_perm': 10000}]

#         drilling_df = pd.DataFrame(self.drilling)

#         drilling_df['diameter_m'] = drilling_df['diameter_in'] * scipy.constants.inch       #0.0254
#         drilling_df['top_msl']    = drilling_df['top_rkb'] - self.header['well_rkb']
#         drilling_df['bottom_msl'] = drilling_df['bottom_rkb'] - self.header['well_rkb']

#         # validate drilling
#         valid_drilling(drilling_df)

#         self.drilling = drilling_df.to_dict()

#     def _process_casings(self):

#         if not self.inventory['casings']:
#             """
#             If no casings table is declared, create a dummy well with info from the header
#             """
#             _well_rkb = self.header['well_rkb']
#             _well_td_rkb = self.header['well_td_rkb']
#             _sf_depth_msl = self.header['sf_depth_msl']
#             _diameter_in = pd.DataFrame(self.drilling)['diameter_in'].min() - 2

#             self.casings = [{'top_rkb': _sf_depth_msl + _well_rkb,
#                              'bottom_rkb': _well_td_rkb,
#                              'diameter_in': _diameter_in,
#                              'toc_rkb': _sf_depth_msl + _well_rkb,
#                              'boc_rkb': _well_td_rkb,
#                              'shoe': True,
#                              'cb_perm': 0.05}]


#         casings_df = pd.DataFrame(self.casings)

#         casings_df['diameter_m'] = casings_df['diameter_in'] * scipy.constants.inch         #0.0254
#         casings_df['top_msl']    = casings_df['top_rkb']    - self.header['well_rkb']
#         casings_df['bottom_msl'] = casings_df['bottom_rkb'] - self.header['well_rkb']
#         casings_df['toc_msl']    = casings_df['toc_rkb']    - self.header['well_rkb']
#         casings_df['boc_msl']    = casings_df['boc_rkb']    - self.header['well_rkb']

#         # validate casings
#         valid_casings(casings_df)

#         self.casings = casings_df.to_dict()

#     def _process_barriers(self):

#         if self.inventory['barriers']:

#             barriers_df = pd.DataFrame(self.barriers)

#             barriers_df['top_msl']    = barriers_df['top_rkb']    - self.header['well_rkb']
#             barriers_df['bottom_msl'] = barriers_df['bottom_rkb'] - self.header['well_rkb']

#             # barriers_df.set_index('barrier_name', inplace=True)
#             self.barriers = barriers_df.to_dict()

#     def _process_geology(self):

#         geology_df = pd.DataFrame(self.geology)

#         geology_df = geology_df.dropna(how='all')
#         geology_df = geology_df.reset_index(drop=True)

#         geology_df['top_msl']  = geology_df['top_rkb'] - self.header['well_rkb']
#         geology_df['base_msl'] = geology_df['top_msl'] - geology_df['top_msl'].diff(periods=-1)
#         geology_df.loc[geology_df.index.max(), 'base_msl'] = self.header['well_td_rkb'] - self.header['well_rkb']

#         self.geology = geology_df.to_dict()

#     @property
#     def to_json(self):
#         return json.dumps(self.__dict__, indent=4)
