from ..compiler.dsl.ast import IntParam
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
    seed_locs = p.var_list(num_islands, CellIdxT, gen=True)
    seed_vals = p.var_dict(seed_locs, Int, gen=True)
    p += seed_locs.distinct()

    land = p.var_dict(grid.C(), sort=Bool, name="land")

    # Puzzle Rules

    # Handle the givens
    # A cell is land if it is given
    p += seed_locs.forall(lambda c: land[c])

    # All 2x2 regions must contain at least one land cell
    p += grid.tiles(size=[2,2], stride=[1,1]).forall(lambda region: region.flat().any(lambda c: land[c]))

    # All water must be connected

    return p.build()