from typing import reveal_type
from ..compiler.dsl import ast
from ..compiler.dsl import Bool, Int
from ..compiler.dsl import PuzzleSpecBuilder, PuzzleSpec
from ..compiler.dsl.libs import std, topo, optional as opt

def build_nurikabe_spec() -> PuzzleSpec:
    p = PuzzleSpecBuilder()
    # Structural parameters
    nR, nC = p.param(sort=Int, name='nR'), p.param(sort=Int, name='nC')
    
    grid = topo.Grid2D(nR, nC)

    # Land + Water domain
    LW_dom, LW_enum = std.Enum('L', 'W')

    # Generator parameters, i.e., the 'clues' of the puzzle
    num_clues = p.gen_var(sort=Int, name='num_clues')
    seed_locs = std.Fin(num_clues).tabulate(lambda i: p.gen_var(dom=grid.cells(), dep=i, name='seed_locs'))
    seed_vals = std.Fin(num_clues).tabulate(lambda i: p.gen_var(sort=Int, dep=i, name='seed_vals'))

    # clue constraints
    p += std.combinations(std.Fin(num_clues), 2).forall(lambda i, j: ~grid.cell_adjacent(4, seed_locs[i], seed_locs[j]))

    # Decision variables, i.e., what the end user will solve for
    vals = ast.as_NDArray(p.func_var(role='D', dom=grid.cells(), codom=LW_dom, name="lw"))
    ## Puzzle Rules

    # No 2x2 water
    p += vals.tiles((2,2),(1,1)).forall(lambda tile: ~tile.forall(lambda v: v==LW_enum.W))

    # Partition into Land and water 
    #lw_doms = LW_dom.tabulate(lambda lw: grid.cells().restrict(lambda c: vals[c]==lw))
    lw_doms = grid.cells().partition(dom=LW_dom, map=lambda c: vals[c])

    # Water must be contiguous
    p += len(lw_doms(LW_enum.W).quotient(grid.adj_eqrel))==1

    islands = std.Fin(num_clues).tabulate(
        lambda i: lw_doms(LW_enum.L).restrict(lambda c: grid.adj_eqrel(c, seed_locs[i]))
    )
    # Must have num_islands islands
    p += std.distinct(islands)

    # Each island must be size of the seed val
    p += islands.forall_enumerate(lambda i, island: len(island)==seed_vals[i])

    # Build the final immutable spec
    return p.build(
        name="Nurikabe",
    )