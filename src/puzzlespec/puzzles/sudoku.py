from ..compiler.dsl.ast import IntParam
from ..compiler.dsl.ir_types import Bool, Int
from ..compiler.dsl.topology import Grid2D as Grid
from ..compiler.dsl.spec import PuzzleSpec


def build_sudoku_spec() -> PuzzleSpec:
    # Grid and Puzzle
    grid = Grid(9, 9)
    p = PuzzleSpec(name="Sudoku", desc="Sudoku", topo=grid)

    # Generator parameters
    given_mask = p.var_dict(grid.C(), sort=Bool)
    given_vals = p.var_dict(grid.C(), sort=Int)
    p.gen_constraints += given_vals.forall(lambda _, v: 1 <= v <= N)

    #p.gen_vars += [given_mask, given_vals]

    # What clues will be visible to the solver
    #p.clues += given_mask.mask(given_vals)

    # Decision variables
    cell_vals = p.var_dict(grid.C(), sort=Int, role="decision")

    # What variables the solver needs to solve.
    #p.solver_vars += (~given_mask).mask(cell_vals)

    # Puzzle Rules
    # Handle the givens
    p.rules += grid.C().forall(lambda c: given_mask[c].implies(cell_vals[c] == given_vals[c]))

    # All values in each row, column, and tile are distinct
    for region in (
        grid.rows(),
        grid.cols(),
        grid.tiles(size=[sqrtN, sqrtN], stride=[sqrtN, sqrtN], as_grid=False),
    ):
        p.rules += region.map(lambda c: cell_vals[c]).distinct()

    return p


