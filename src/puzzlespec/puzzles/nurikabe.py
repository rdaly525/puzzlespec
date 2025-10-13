from ..compiler.dsl.ast import IntParam
from ..compiler.dsl import ast
from ..compiler.dsl.ir_types import Bool, Int, CellIdxT
from ..compiler.dsl.topology import Grid2D as Grid
from ..compiler.dsl.spec_builder import PuzzleSpecBuilder
from ..compiler.dsl.spec import PuzzleSpec


def build_nurikabe_spec() -> PuzzleSpec:
    nR, nC = IntParam("nR"), IntParam("nC")
    grid = Grid(nR, nC)
    p = PuzzleSpecBuilder(name="Nurikabe", desc="Nurikabe", topo=grid)

    # Generator parameters
    num_islands = p.var(sort=Int, gen=True, name="num_islands")
    seed_mask = p.var_dict(grid.C(), sort=Bool, gen=True, name='seed_mask')
    seed_p = lambda c: seed_mask[c]
    seed_vals = p.var_dict(grid.C(), sort=Int, gen=True, name='seed_vals')
    seed_val = lambda c: seed_val[c]
    p += (seed_mask.count() == num_islands)

    land = p.var_dict(grid.C(), sort=Bool, name="land", gen=True)
    land_p = lambda c: land[c]
    water_p = lambda c: ~land[c]

    # Puzzle Rules

    # Handle the givens
    # A cell is land if it is given
    p += grid.C().forall(lambda c: seed_mask[c].implies(land[c]))

    # All 2x2 regions must contain at least one land cell
    p += grid.tiles(size=[2,2], stride=[1,1]).forall(lambda region: region.flat().any(lambda c: land[c]))

    # All water must be connected
    # Partition water into groups then make sure there is only 1 group
    
    water_groups = grid.partition(
        "C",
        Closure(lambda c1, c2: water_p(c1) & water_p(c2) & grid.is_neighbor(4,c1,c2))
    )
    p += len(water_groups) == 1

    # Islands
    # Partion land into groups (islands) (implicit key)
    islands = grid.partition(
        "C",
        Closure(lambda c1, c2: land_p(c1) & land_p(c2) & grid.is_neighbor(4,c1,c2))
    )
    # Check number of islands
    p += len(islands)==num_islands

    # Each island has exactly 1 seed
    islands.forall_group(lambda island: grid.C().map(lambda c: seed_mask[c] & (c in island)) ==1)

    # The seed of that island is the size of the island
    islands.forall_group(lambda island: grid.C().exists(lambda c: seed_mask[c] & (c in island) & len(island)==seed_vals[c]))


    # ALTERNATIVLY
    # All water must be connected
    
    grid.C().color(land_p)


    return p.build()