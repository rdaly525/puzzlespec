from puzzlespec import fin, var, func_var, Int, PuzzleSpecBuilder, VarSetter
from puzzlespec.libs import std, optional as opt

# Spec Builder
p: PuzzleSpecBuilder = PuzzleSpecBuilder()

# Define Parameters
N = var(Int, name='N')
box_dim = var(Int, name='box_dim')

# Constraints on Parameters!
p += (box_dim > 0) & (box_dim*box_dim==N)

# Alternatively using refinement types
# box_dim = var(dom=Int.U.restrict(lambda bd: (bd > 0) & (bd*bd==N))

# Value domain (1..N)
Digits = std.range(1, N) # Domain of values {1..N}

# Grid structure
Cells = fin(N)*fin(N)

# Decision variables
cell_vals = func_var(dom=Cells, codom=Digits, name="cell_vals")

# All values in each box, row, column, and Box are distinct
p += cell_vals.tiles(size=[box_dim, box_dim], stride=[3,3]).forall(lambda region: std.distinct(region))
p += cell_vals.cols().forall(lambda region: std.distinct(region))
p += cell_vals.cols().forall(lambda region: std.distinct(region))
# Givens

# The Given clues of the puzzle
DigitsOpt = opt.optional_dom(Digits) # Dom[𝟙] ⊎ Digits 
givens = func_var(dom=Cells, codom=DigitsOpt, name="givens")


# Given vals must be consistent with cell_vals
p += Cells.forall(
    lambda c: opt.fold(givens(c), on_none=True, on_some=lambda v: cell_vals(c)==v)
)

# German Whispers
gw = True
if gw:
    from puzzlespec.libs.topology import Grid2D
    grid = Grid2D(N, N)
    whispers = fin(var(sort=Int, name='num_whispers')).map(
        lambda i: fin(var(sort=Int, indices=(i,), name='whisper_lens')).map(
            lambda j: var(dom=Cells, indices=(i, j), name='whispers_locs')
        )
    )
    
    # structural constraint: German whisper cells must be neighbors
    p += whispers.forall(
        lambda whisper: whisper.windows(2).forall(
            lambda cells: grid.cell_adjacent(cells[0], cells[1])
        )
    )

    # puzzle rule: neighboring whisper cells must have a difference of at least 5
    p += whispers.forall(
        lambda whisper: whisper.windows(2).forall(
            lambda cells: abs(cell_vals(cells[0])-cell_vals(cells[1])) >= 5
        )
    )




spec = p.build("Sudoku")
print(spec)
print("OPTIMIZED SPEC")
print(spec.optimize())

#setter = VarSetter(spec)
#setter.N=9
#spec9 = setter.build()
#print(spec9.optimize())