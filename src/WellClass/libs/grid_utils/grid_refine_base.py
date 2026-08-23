from typing import List

import numpy as np
import pandas as pd

from .grid_coarse import GridCoarse
from .LGR_bbox import compute_bbox
from .LGR_grid_utils import compute_ngrd


class GridRefineBase:
    def __init__(self, grid_coarse: GridCoarse, LGR_sizes_x: List[float], LGR_sizes_y: List[float], LGR_sizes_z: np.ndarray, min_grd_size: float):
        """dataframe for LGR mesh for the center coarse cell

        Args:

            grid_coarse (GridCoarse): information on coarse grid
            LGR_sizes_x (list[float]): LGR x grid intervals
            LGR_sizes_y (list[float]): LGR y grid intervals
            LGR_sizes_z (np.ndarray): LGR DZ inernals
            min_grd_size (float): minimize grid size
        """

        self.min_grd_size = min_grd_size

        # dx/dy of coarse grid
        self.main_grd_dx = grid_coarse.main_grd_dx
        self.main_grd_dy = grid_coarse.main_grd_dy

        # LGR dimensions
        nx = len(LGR_sizes_x)
        ny = len(LGR_sizes_y)
        nz = len(LGR_sizes_z)

        print(f"LGR dimension: nx={nx}, ny={ny}, nz={nz}")

        # set dimensions
        self.nx, self.ny, self.nz = nx, ny, nz

        # Create i, j, k indices
        cell_ijk = np.indices((nx, ny, nz))
        cell_ijk = cell_ijk.reshape((3, nx * ny * nz)).T

        # Create LGR Dataframe with indices
        mesh_df = pd.DataFrame(data=cell_ijk, columns=["i", "j", "k"])

        # TODO(hzh): why not in the order of ['k', 'j']?
        mesh_df.sort_values(by=["k", "i"], inplace=True)
        mesh_df.reset_index(inplace=True, drop=True)

        #
        self.mesh_df = mesh_df

        # set up fields
        self._set_cell_intervals(self.mesh_df, LGR_sizes_x, LGR_sizes_y, LGR_sizes_z)
        self._set_cell_coords(self.mesh_df)
        self._set_z_corners(self.mesh_df)

        # indices for center finer grid
        mid_i = grid_coarse.main_grd_i
        mid_j = grid_coarse.main_grd_j

        self._upscale_properties(grid_coarse.grid_init, mid_i, mid_j)

    def _set_cell_intervals(self, mesh_df: pd.DataFrame, LGR_sizes_x: List[float], LGR_sizes_y: List[float], LGR_sizes_z: np.ndarray):
        """Creat DX, DY, DZ for LGR mesh

        Args:

            mesh_df (pd.DataFrame): dataframe for LGR mesh of the center coarse cell
            LGR_sizes_x (list[float]): LGR x grid intervals
            LGR_sizes_y (list[float]): LGR y grid intervals
            LGR_sizes_z (np.ndarray): LGR DZ grid inernals
        """

        # mesh
        DX_grid, DZ_grid, DY_grid = np.meshgrid(LGR_sizes_x, LGR_sizes_z, LGR_sizes_y)

        # internals
        mesh_df["DX"] = DX_grid.flatten()
        mesh_df["DY"] = DY_grid.flatten()
        mesh_df["DZ"] = DZ_grid.flatten()

    def _set_cell_coords(self, mesh_df):
        """Create cell coordinate X, Y, Z for LGR mesh

        Args:

            mesh_df (pd.DataFrame): dataframe for LGR mesh of the center coarse cell
        """

        # cell coordinates
        xcoord = (mesh_df.query("j==0&k==0").DX.cumsum() - mesh_df.query("j==0&k==0").DX / 2).values
        ycoord = (mesh_df.query("i==0&k==0").DY.cumsum() - mesh_df.query("i==0&k==0").DY / 2).values
        zcoord = (mesh_df.query("i==0&j==0").DZ.cumsum() - mesh_df.query("i==0&j==0").DZ / 2).values

        # TODO(hzh): a bug?
        # map_X = dict(zip(mesh_df.query("j==0&j==0")['i'], xcoord))
        map_X = dict(zip(mesh_df.query("j==0&k==0")["i"], xcoord))
        map_Y = dict(zip(mesh_df.query("i==0&k==0")["j"], ycoord))
        map_Z = dict(zip(mesh_df.query("i==0&j==0")["k"], zcoord))

        # save cell coordinates X, Y, Z to dataframe
        mesh_df["X"] = mesh_df["i"].map(map_X)
        mesh_df["Y"] = mesh_df["j"].map(map_Y)
        mesh_df["Z"] = mesh_df["k"].map(map_Z)

    def _set_z_corners(self, mesh_df):
        """save Corner Z points to dataframe

        Args:

            mesh_df (pd.DataFrame): dataframe for LGR mesh of the center coarse cell
        """

        mesh_df["Zcorn_top"] = mesh_df["Z"] - mesh_df["DZ"] / 2
        mesh_df["Zcorn_bottom"] = mesh_df["Z"] + mesh_df["DZ"] / 2

    def _upscale_properties(self, grid_coarse: GridCoarse, mid_i: int, mid_j: int):
        """Upscale coarse properties to LGR mesh

        Args:
            grid_coarse (GridCoarse): information on coarse grid
            mid_i (int): x index of center cell on the coarse grid
            mid_j (int): y index of center cell on the coarse grid
        """

        # for convenience only
        mesh_df = self.mesh_df

        # properties
        fields = ["PORV", "PERMX", "PERMY", "PERMZ", "MULTX", "MULTY", "MULTZ", "MULTX-", "MULTY-", "MULTZ-", "PORO"]

        # Upscale coarse properties to LGR grids

        for field in fields:
            # mesh_df[field] = np.nan
            mesh_df[field] = 0.0  # TODO(hzh): what should I put here?

        for idx, row in grid_coarse.query("i==@mid_i & j==@mid_j").iterrows():
            # switch to corner coords, coarse grid
            top = row.Z - row.DZ / 2
            base = row.Z + row.DZ / 2

            for field in fields:
                mesh_df.loc[(mesh_df["Z"] >= top) & (mesh_df["Z"] < base), field] = row[field]

    def _set_material_type(self, holes_df: pd.DataFrame, casings_df: pd.DataFrame, barrier_regions_df: pd.DataFrame) -> None:
        """Assign material types, such as openholes, overburden, cement bond, etc.

        Args:
            holes_df (pd.DataFrame): drilled-hole intervals
            casings_df (pd.DataFrame): information about casings and cement-bond
            barrier_regions_df (pd.DataFrame): GaP barrier material regions
        """

        # only for convenience
        mesh_df = self.mesh_df

        # set default material to 'overburden'
        mesh_df["material"] = "overburden"

        # ### 1. Drilling
        for idx, row in holes_df.iterrows():
            top, bottom = row["top_msl"], row["bottom_msl"]  # noqa: F841

            if top < mesh_df["Zcorn_bottom"].max():
                # extract bounding box
                k_min, k_max = row["k_min"], row["k_max"]
                ij_min, ij_max = row["ij_min"], row["ij_max"]

                # 1.1 set material type to openhole
                criteria = "(k >= @k_min)  & (k <= @k_max) & \
                             (i >= @ij_min) & (i <= @ij_max) & \
                             (j >= @ij_min) & (j <= @ij_max)"
                mesh_df.loc[mesh_df.eval(criteria), "material"] = "openhole"

        # ### 2. Casings
        for ic, (idx, row) in enumerate(casings_df.iterrows()):
            # extract bounding box
            k_min, k_max = row["k_min"], row["k_max"]  # noqa: F841
            ij_min, ij_max = row["ij_min"], row["ij_max"]  # noqa: F841
            toc_k_min, toc_k_max = row["toc_k_min"], row["toc_k_max"]  # noqa: F841

            # 2.1 set material type to annulus
            # x
            criteria_i = '(material == "openhole") & \
                           (k >= @k_min) & (k <= @k_max) & \
                            ((i < @ij_min) | (i > @ij_max))'
            mesh_df.loc[mesh_df.eval(criteria_i), "material"] = "annulus"
            # y
            criteria_j = '(material == "openhole") & \
                           (k >= @k_min) & (k <= @k_max) & \
                           ((j < @ij_min) | (j > @ij_max))'
            mesh_df.loc[mesh_df.eval(criteria_j), "material"] = "annulus"

            # 2.2 set material type to cement_bond
            criteria = '(material == "annulus") & \
                        (k >= @toc_k_min) & (k <= @toc_k_max)'
            mesh_df.loc[mesh_df.eval(criteria), "material"] = f"cement_bond_{ic}"

        # ### 3. Barriers
        for ib, (idx, row) in enumerate(barrier_regions_df.iterrows()):
            b_k_min, b_k_max = row["k_min"], row["k_max"]  # noqa: F841

            criteria = '(material == "openhole") & \
                        (k >= @b_k_min) & (k <= @b_k_max)'
            mesh_df.loc[mesh_df.eval(criteria), "material"] = f"barrier_{ib}"

    def _set_permeability(self, holes_df: pd.DataFrame, casings_df: pd.DataFrame, barrier_regions_df: pd.DataFrame) -> None:
        """Actual function to assign permeability according to material type

        Args:
            holes_df (pd.DataFrame): drilled-hole intervals
            casings_df (pd.DataFrame): information about casings and cement-bond
            barrier_regions_df (pd.DataFrame): GaP barrier material regions
        """

        # for convenience only
        mesh_df = self.mesh_df

        # set permeability according to material type

        # 1. openhole
        oh_perm = holes_df["oh_perm"].iloc[0]
        criteria = 'material == "openhole"'
        mesh_df.loc[mesh_df.eval(criteria), "PERMX"] = oh_perm

        # 2. cement bond
        for ic, (_, row) in enumerate(casings_df.iterrows()):
            cb_perm = row["cb_perm"]
            criteria = f'material == "cement_bond_{ic}"'
            mesh_df.loc[mesh_df.eval(criteria), "PERMX"] = cb_perm

        # 3. barrier
        for ib, (_, row) in enumerate(barrier_regions_df.iterrows()):
            barrier_perm = row["barrier_perm"]
            criteria = f'material == "barrier_{ib}"'
            mesh_df.loc[mesh_df.eval(criteria), "PERMX"] = barrier_perm

    def _compute_num_lateral_fine_grd(self, holes_df: pd.DataFrame, casings_df: pd.DataFrame, barrier_regions_df: pd.DataFrame):
        """compute number of fine grid in x-y directions

        Args:
            holes_df (pd.DataFrame): drilled-hole intervals
            casings_df (pd.DataFrame): information about casings and cement-bond
            barrier_regions_df (pd.DataFrame): GaP barrier material regions
        """
        # for convenience
        min_grd_size = self.min_grd_size

        # n_grd_id for well elements
        holes_df["n_grd_id"] = holes_df["diameter_m"].map(lambda x: compute_ngrd(x, min_grd_size))
        casings_df["n_grd_id"] = casings_df["diameter_m"].map(lambda x: compute_ngrd(x, min_grd_size))
        barrier_regions_df["n_grd_id"] = barrier_regions_df["diameter_m"].map(lambda x: compute_ngrd(x, min_grd_size))

        # borehole_df['n_grd_id'] = borehole_df['id_m'].map(lambda x: compute_ngrd(x, min_grd_size))

    def _compute_bbox(self, holes_df: pd.DataFrame, casings_df: pd.DataFrame, barrier_regions_df: pd.DataFrame) -> None:
        """Compute bounding boxes for drillings, casings and barriers.

        Args:
            holes_df (pd.DataFrame): drilled-hole intervals
            casings_df (pd.DataFrame): information about casings and cement-bond
            barrier_regions_df (pd.DataFrame): GaP barrier material regions
        """

        # for convenience
        mesh_df = self.mesh_df
        nxy = self.nx

        # depth cut off
        maxDepth = mesh_df["Zcorn_bottom"].max()

        # ### 1. Drillings
        compute_bbox(mesh_df, holes_df, nxy=nxy, maxDepth=maxDepth)

        # ### 2. Casings
        compute_bbox(mesh_df, casings_df, nxy=nxy, maxDepth=maxDepth, is_casing=True)

        # ### 3. Barriers
        compute_bbox(mesh_df, barrier_regions_df, nxy=nxy, maxDepth=maxDepth)

    def _compute_bbox_gap_casing(self, casings_df: pd.DataFrame) -> pd.DataFrame:
        """compute bbox of casing for GaP

        Args:
            casings_df (pd.DataFrame): information about casings and cement-bond

        Returns:
            an updated dataframe specifically for GaP code
        """

        # for convenience
        mesh_df = self.mesh_df
        nxy = self.nx
        min_grd_size = self.min_grd_size

        # generate new pd.DataFrame by trimming casings
        # gap_casing_df = trim_casings_cement(casings_df)
        gap_casing_df = casings_df

        # compute number of lateral grid (refined)
        gap_casing_df["n_grd_id"] = casings_df["diameter_m"].map(lambda x: compute_ngrd(x, min_grd_size))

        # Casings
        compute_bbox(mesh_df, gap_casing_df, nxy=nxy, is_casing=True)

        return gap_casing_df
