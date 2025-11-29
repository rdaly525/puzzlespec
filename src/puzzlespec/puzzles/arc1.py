from ..compiler.dsl.ir_types import Bool, Int
from ..compiler.dsl.spec_builder import PuzzleSpecBuilder
from ..compiler.dsl.spec import PuzzleSpec
from ..compiler.dsl.libs import std, optional as opt, topo


def build_arc1() -> PuzzleSpec:
    # Grid and Puzzle
    p: PuzzleSpecBuilder = PuzzleSpecBuilder()
    # 
    color_dom, color_enum = std.Enum('r','g','b')
    nR, nC = p.param(sort=Int, name='nR'), p.param(sort=Int, name='nC')
    # Underlying grid
    grid = topo.Grid2D(nR, nC)
    raw_input = grid.cells().tabulate(lambda c: p.param(dom=color_dom, name="raw_input"))

    # Generator parameters
    num_clues = p.gen_var(sort=Int, name='num_clues')
    givens = p.func_var(role='G', dom=grid.cells(), codom=opt.Optional(digits), name="givens")
    # clue constraints
    p += opt.count_some(givens)==num_clues
    
    # Decision variables
    cell_vals = p.decision_var(dom=grid.cells(), codom=digits, name="cell_vals")
    
    # Puzzle Rules
    
    # Given vals must be consistent with cell_vals
    p += grid.cells().forall(
        lambda c: opt.fold(givens[c], on_none=True, on_some=lambda v: cell_vals[c]==v)
    )
 