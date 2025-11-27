from ..compiler.dsl.spec_builder import PuzzleSpecBuilder
from ..compiler.dsl.spec import PuzzleSpec
from ..compiler.dsl.libs import std, optional as opt, topo
from ..compiler.dsl import ir, Int


def build_sudoku_spec(gw=False) -> PuzzleSpec:
    # Grid and Puzzle
    p: PuzzleSpecBuilder = PuzzleSpecBuilder()
    # Value domain (1..9)
    digits = std.Range(1, 10)

    # Underlying grid
    grid = topo.Grid2D(9, 9)

    # Generator parameters
    #T = ir.PiT(
    #    grid.cells().node,
    #    ir._LambdaTPlaceholder(
    #        ir._BoundVarPlaceholder(ir.TupleT(ir.IntT(), ir.IntT()), _map_dom=std.Fin(2)), 
    #        opt.Optional(digits).carT
    #    )
    #)
    #givens = p.gen_var(sort=T, name='givens') # Cell -> Optional[Bool]
    num_clues = p.gen_var(sort=Int, name='num_clues')
    givens = p.func_var(role='G', dom=grid.cells(), codom=opt.Optional(digits), name="givens")
    #givens = grid.cells().map(lambda c: p.var(role='G', codom=opt.Optional(digits), name='givens', dep=(c,)))
    # clue constraints
    p += opt.count_some(givens)==num_clues
    
    cell_vals = p.func_var(role='D', dom=grid.cells(), codom=digits, name="cell_vals")
    #vals = p.func_var(role='D', dom=std.Fin(5), codom=digits, name="vals")
    #p += vals.apply(2)==1
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

    for rct in (
        grid.cells().rows(),
        grid.cells().cols(),
        grid.cells().tiles(size=[3,3], stride=[3,3]),
    ):
        p += rct.forall(lambda region: std.distinct(cell_vals[region]))

    gw = True
    # german whispers
    if gw:
        # german whisper 'megavar'
        whispers = std.Fin(p.var(role='G',sort=Int, name='num_whispers')).map(
            lambda i: std.Fin(p.var(role='G', sort=Int, dep=i, name='whisper_lens')).map(
                lambda j: p.var(role='G', dom=grid.cells(), dep=(i, j), name='whispers_locs')
            )
        )
        # structural constraint: German whisper cells must be neighbors
        p += whispers.forall(
            lambda whisper: whisper.windows(size=2,stride=1).map(
                lambda cells: grid.cell_adjacent(8, cells[0], cells[1])
            )
        )

        # puzzle rule: neighboring whisper cells must have a difference of at least 5
        #p += whispers.forall(
        #    lambda whisper: whisper.windows(2).map(
        #        lambda cells: (whisper[cells[0]]-whisper[cells[1]]).abs() >= 5
        #    )
        #)


    return p.build('sudoku')
