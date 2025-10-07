from ..compiler.dsl.ast import IntParam
from ..compiler.dsl.ir_types import Bool, Int
from ..compiler.dsl.topology import Grid2D as Grid
from ..compiler.dsl.spec_builder import PuzzleSpecBuilder
from ..compiler.dsl.spec import PuzzleSpec


def build_sudoku_spec() -> PuzzleSpec:
    # Grid and Puzzle
    grid = Grid(9, 9)
    p = PuzzleSpecBuilder(name="Sudoku", desc="Sudoku", topo=grid)

    # Generator parameters
    given_mask = p.var_dict(grid.C(), sort=Bool, gen=True, name="given_mask")
    given_vals = p.var_dict(grid.C(), sort=Int, gen=True, name="given_vals")
    p += grid.C().forall(lambda c: given_vals[c].between(1, 9))

    # Decision variables
    cell_vals = p.var_dict(grid.C(), sort=Int, name="cell_vals")

    # Puzzle Rules
    
    # Handle the givens
    p += grid.C().forall(lambda c: given_mask[c].implies(cell_vals[c] == given_vals[c]))

    # All values in each row, column, and tile are distinct
    for rc in (
        grid.rows(),
        grid.cols(),
    ):
        p += rc.forall(lambda region: region.distinct())
    p += grid.tiles(size=[3,3], stride=[3,3]).forall(lambda region: region.flat().distinct())


    return p.build()