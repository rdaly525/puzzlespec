from typing import Optional
from ..compiler.dsl import ast, ir
from ..compiler.dsl.spec_builder import PuzzleSpecBuilder, PuzzleSpec
from ..libs import std, topology as topo, optional as opt, std, var_def as v
from ..compiler.dsl import ir


def build_sudoku_spec(gw=False) -> PuzzleSpec:
    Int = ast.IntType(ir.IntT())
    # Grid and Puzzle
    p: PuzzleSpecBuilder = PuzzleSpecBuilder()
    # Value domain (1..9)
    digits = std.range(1, 10)

    # Underlying grid
    grid = topo.Grid2D(9, 9)

    # Generator parameters (i.e., the 'clues' of the puzzle)
    num_clues = v.gen_var(sort=Int, name='num_clues')
    givens = v.func_var(role='G', dom=grid.cells(), codom=opt.optional_dom(digits), name="givens")

    # clue constraints
    p += opt.count_some(givens)==num_clues
    
    # Decision variables
    cell_vals = v.func_var(role='D', dom=grid.cells(), codom=digits, name="cell_vals")

    # Puzzle Rules
    
    # Given vals must be consistent with cell_vals
    p += grid.cells().forall(
        lambda c: opt.fold(givens(c), on_none=True, on_some=lambda v: cell_vals(c)==v)
    )
    
    # All values in each row, column, and tile are distinct
    for rct in (
        cell_vals.rows(),
        cell_vals.cols(),
        cell_vals.tiles(size=[3,3], stride=[3,3]),
    ):
        p += rct.forall(lambda region: std.distinct(region))

    gw = False
    # german whispers
    if gw:
        # german whisper 'megavar'
        whispers = std.Fin(p.var(role='G',sort=Int, name='num_whispers')).map(
            lambda i: std.Fin(p.var(role='G', sort=Int, indices=(i,), name='whisper_lens')).map(
                lambda j: p.var(role='G', dom=grid.cells(), indices=(i, j), name='whispers_locs')
            )
        )
        #whisper = std.Fin(8).map(lambda i: p.var(role='G', dom=grid.cells(), name='whisper', indices=(i,)))
        #p += whisper.windows(2).forall(lambda cells2: cells2[0]==(3,4))
        #p += whisper.windows(2).forall(lambda cells2: cells2[1]==(3,4))
        # structural constraint: German whisper cells must be neighbors
        p += whispers.forall(
            lambda whisper: whisper.windows(2).forall(
                lambda cells: grid.cell_adjacent(8, cells[0], cells[1])
            )
        )

        # puzzle rule: neighboring whisper cells must have a difference of at least 5
        p += whispers.forall(
            lambda whisper: whisper.windows(2).forall(
                lambda cells: abs(cell_vals(cells(0))-cell_vals(cells(1))) >= 5
            )
        )


    return p.build('sudoku')
