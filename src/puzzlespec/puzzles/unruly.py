from typing import Optional
from ..compiler.dsl import ast, ir
from ..compiler.dsl.spec_builder import PuzzleSpecBuilder, PuzzleSpec
from ..libs import std, topology as topo, optional as opt, std
from ..compiler.dsl import ir


def build_unruly_spec() -> PuzzleSpec:
    Int = ast.IntType(ir.IntT())
    Bool = ast.BoolType(ir.BoolT())
    p = PuzzleSpecBuilder()
    
    # Structural parameters
    nR, nC = ps.param(sort=Int, name='nR'), ps.param(sort=Int, name='nC')

    # Structural constraints
    p += [nR % 2 == 0, nC % 2 == 0]

    grid = topo.Grid2D(nR, nC)

    # color domain (black and white)
    BW_dom, BW_enum = std.enum('B', 'W')

    # Generator variables, i.e., the 'clues' of the puzzle
    num_clues = p.gen_var(sort=Int, name='num_clues')
    givens = p.func_var(role='G', dom=grid.cells(), codom=opt.optional_dom(BW_dom), name='givens') # Cell -> Optional[BW_enum]

    # clue constraints
    p += opt.count_some(givens)==num_clues

    ## Decision variables, i.e., what the end user will solve for
    color = p.func_var(role='D', dom=grid.cells(), codom=BW_dom, name='color') # Cell -> BW_enum

    ### Puzzle Rules
    ## Handle the givens
    p += grid.cells().forall(
        lambda c: opt.fold(givens(c), on_none=True, on_some=lambda v: color(c)==v)
    )

    ### Equal balance of colors in all rows and cols
    p += grid.cells().rows().forall(lambda row: std.count(color[row], lambda v: v==BW_enum.B) == nC // 2)
    p += grid.cells().cols().forall(lambda col: std.count(color[col], lambda v: v==BW_enum.B) == nR // 2)

    ### No triple of the same color
    p += grid.cells().rows().forall(
        lambda line: line.windows(size=3, stride=1).forall(
            lambda w: ~std.all_same(color[w])
        )
    )
    p += grid.cells().cols().forall(
        lambda line: line.windows(size=3, stride=1).forall(
            lambda w: ~std.all_same(color[w])
        )
    )


    # Build the final immutable spec
    return p.build(
        name="Unruly",
    )