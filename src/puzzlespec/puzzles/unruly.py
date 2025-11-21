from ..compiler.dsl import ast
from ..compiler.dsl import Bool, Int
from ..compiler.dsl import PuzzleSpecBuilder, PuzzleSpec
from ..compiler.dsl.libs import std, topo, optional as opt
from ..compiler.dsl import ir


def build_unruly_spec() -> PuzzleSpec:
    p = PuzzleSpecBuilder()
    
    # Structural parameters
    nR, nC = p.param(sort=Int, name='nR'), p.param(sort=Int, name='nC')

    # Structural constraints
    p += [nR % 2 == 0, nC % 2 == 0]

    grid = topo.Grid2D(nR, nC)

    # color domain (black and white)
    BW_dom, BW_enum = std.Enum('B', 'W')

    # Generator parameters, i.e., the 'clues' of the puzzle
    num_clues = p.gen_var(sort=Int, name='num_clues')
    T = ir.FuncT(grid.cells().node, opt.Optional(BW_dom).carT)
    givens = p.gen_var(sort=T, name='givens') # Cell -> Optional[Bool]
    #givens = grid.cells().map(
    #    lambda c: p.gen_var(dom=opt.Optional(BW_dom), dep=c, name='givens') # Cell -> Optional[Bool]
    #)

    # clue constraints
    p += opt.count_some(givens)==num_clues

    # Decision variables, i.e., what the end user will solve for
    T = ir.FuncT(grid.cells().node, BW_dom.carT)
    color = p.decision_var(sort=T, name='color')
    #color = p.func_var(role='D', dom=grid.cells(), codom=BW_dom, name="color")

    ## Puzzle Rules

    # Handle the givens
    p += grid.cells().forall(
        lambda c: opt.fold(givens(c), on_none=True, on_some=lambda v: color(c)==v)
    )

    ## Equal balance of colors in all rows and cols
    p += grid.cells().rows().forall(lambda row: std.count(color[row], lambda v: v==BW_enum.B) == nC // 2)
    p += grid.cells().cols().forall(lambda col: std.count(color[col], lambda v: v==BW_enum.B) == nR // 2)

    ## No triple of the same color
    rows = grid.cells().rows()
    p += rows.forall(
        lambda line: line.windows(3).forall(
            lambda w: ~std.all_same(color[w])
        )
    )
    p += grid.cells().cols().forall(
        lambda line: line.windows(3).forall(
            lambda w: ~std.all_same(color[w])
        )
    )


    # Build the final immutable spec
    return p.build(
        name="Unruly",
    )