from puzzlespec import var, func_var, Unit, Int, U, PuzzleSpecBuilder, VarSetter
from puzzlespec.libs import std, nd

# Spec Builder
p: PuzzleSpecBuilder = PuzzleSpecBuilder()

####################################
# Define Parameters as *Variables* #
####################################
# Grid dim as N x N
N = var(Int, name='N')

# Box size as sqrt(N)
#box_size = var(Int, name='box_size')
# Constraints on parameters (N must be a perfect square)
#p += [box_size*box_size == N, box_size >= 0]

##############################
# Domains are typed *values* #
##############################

# Grid structure: Domain of Cell indices
Cells = nd.fin(N)*nd.fin(N)

# Domain for decision variables
Digits = nd.range(1, N+1) # [1..N)

#############################
# Supports refinement types # 
#############################
# Alternate definition of box_size:  {i: Int | i >=0 & i*i==N}
refinement_dom = U(Int).restrict(lambda i: (i >= 0) & (i*i==N))
box_size = var(dom=refinement_dom, name='bs')

#########################
# Functions are *total* #
#########################
# variables can be functions.
cell_digits = func_var(Cells, Digits, name="cell_digits") # Cells -> Digits
#cell_digits = func_var(nd.fin(N), Digits, name="cell_digits") # Cells -> Digits
#p += cell_digits.forall(lambda d: d > 2)

##############################
# Quantifcation over domains #
##############################
# Row constraint (numpy-style syntax)
#row_func = nd.fin(N).empty_func()
#for r in nd.fin(N):
#    row_func[r] = std.distinct(cell_digits[Cells[r,:]])
#p += row_func.forall()

# Alternate syntax
p += nd.rows(cell_digits).forall(lambda row_vals: std.distinct(row_vals))
p += nd.cols(cell_digits).forall(lambda col_vals: std.distinct(col_vals))

# Box constraint
p += nd.tiles(
    cell_digits,
    size=(box_size, box_size),
    stride=(box_size, box_size)
).forall(lambda box_vals: std.distinct(box_vals))

#####################
# Clues as Sum Type #
#####################
OptionalDigits = U(Unit) + Digits # Dom[𝟙] ⊎ Digits 
givens = func_var(Cells, OptionalDigits, name="givens")

# Given vals must be consistent with cell_digits
p += Cells.forall(
    lambda c: givens(c).match(      # pattern match for clue
        lambda _: True,             # True if Unit
        lambda d: cell_digits(c)==d # Same as cell_digit if given
    )
)

spec = p.build("Sudoku")
#print("UNOPTIMIZED SPEC")
#print(spec)
#input()
#print("OPTIMIZED SPEC")
print(spec.optimize())
#input()
print("SETTING N = 9")
setter = VarSetter(spec)
setter.N = 9
spec9 = setter.build()
print(spec9.optimize())



# German Whispers
gw = False
if gw:
    from puzzlespec.libs.topology import Grid2D
    grid = Grid2D(N, N)
    whispers = fin(var(sort=Int, name='num_gw')).map(
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
            lambda cells: abs(cell_digits(cells[0])-cell_digits(cells[1])) >= 5
        )
    )

# API for directly assigning variables
