from ..compiler.dsl import ast
from ..compiler.dsl.ir_types import Bool, Int
from ..compiler.dsl import PuzzleSpecBuilder, PuzzleSpec
from ..compiler.dsl.topology import Grid2D as Grid


def build_unruly_spec() -> PuzzleSpec:
    # Structural parameters
    nR, nC = ast.IntParam("nR"), ast.IntParam("nC")

    # Grid and Spec Builder
    grid = Grid(nR, nC)
    p = PuzzleSpecBuilder(
        name="Unruly",
        desc='''
        Unruly is a puzzle where you have to color a grid such that each row and column has an equal number of colors.
        ''',
        topo=grid,
    )
    # Structural constraints
    p += [nR % 2 == 0, nC % 2 == 0, nR > 1, nC > 1]

    # Generator parameters, i.e., the 'clues' of the puzzle
    num_clues = p.var(sort=Int, gen=True, name='num_clues')
    given_mask = p.var_dict(grid.C(), sort=Bool, name='given_mask', gen=True) # Cell -> Var
    given_vals = p.var_dict(grid.C(), sort=Bool, name='given_vals', gen=True) # Cell -> Var

    # clue constraints
    p += given_mask[grid.C()].sum()==num_clues

    # Decision variables, i.e., what the end user will solve for
    color = p.var_dict(grid.C(), sort=Bool, name="color", gen=False)

    ## Puzzle Rules

    # Handle the givens
    p += grid.cells().forall(lambda c: given_mask[c].implies(color[c] == given_vals[c]))

    ## Equal balance of colors in all rows and cols
    p += grid.rows().forall(lambda row: color[row].sum() == nC // 2)
    p += grid.cols().forall(lambda col: color[col].sum() == nR // 2)

    ## No triple of the same color
    p += grid.rows().forall(
        lambda row: row.windows(3).forall(
            lambda w: (color[w].sum() != 3) & (color[w].sum() != 0)
        )
    )
    p += grid.cols().forall(
        lambda col: col.windows(size=3, stride=1).forall(
            lambda win: (color[win].sum() != 3) & (color[win].sum() != 0)
        )
    )

    # Build the final immutable spec
    return p.build()