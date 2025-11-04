from ..compiler.dsl import ast
from ..compiler.dsl.ir_types import Bool, Int
from ..compiler.dsl import PuzzleSpecBuilder, PuzzleSpec
from ..compiler.dsl.lib import std, topo, optional as opt

def build_unruly_spec() -> PuzzleSpec:
    p = PuzzleSpecBuilder()
    # Structural parameters
    nR, nC = p.param(sort=Int, name='nR'), p.param(sort=Int, name='nC')
    # Structural constraints
    p += [nR % 2 == 0, nC % 2 == 0, nR > 1, nC > 1]

    grid = topo.Grid2D(nR, nC)

    # color domain (black and white)
    BW_dom, BW_enum = std.Enum('B', 'W')

    # Generator parameters, i.e., the 'clues' of the puzzle
    num_clues = p.gen_var(sort=Int, name='num_clues')
    givens = p.gen_var(dom=grid.cells(), codom=opt.Optional(BW_dom), name='givens') # Cell -> Optional[Bool]

    # clue constraints
    p += opt.count_some(givens)==num_clues

    # Decision variables, i.e., what the end user will solve for
    color = p.decision_var(dom=grid.cells(), codom=BW_dom, name="color")

    ## Puzzle Rules

    # Handle the givens
    p += grid.cells().forall(
        lambda c: opt.fold(givens[c], on_none=True, on_some=lambda v: color[c]==v)
    )

    ## Equal balance of colors in all rows and cols
    p += grid.cells().rows().forall(lambda row: std.count(color[row], lambda v: v==BW_enum.B) == nC // 2)
    p += grid.cells().rows().forall(lambda row: std.count(color[row], lambda v: v==BW_enum.B) == nR // 2)

    ## No triple of the same color
    for rcs in (grid.rows(), grid.cols()):
        p += rcs.forall(
            lambda line: line.windows(3).forall(
                lambda w: ~std.all_same(color[w])
            )
        )

    # Build the final immutable spec
    return p.build(
        name="Unruly",
    )