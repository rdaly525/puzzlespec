from puzzlespec import fin, var, func_var, Unit, Int, U, PuzzleSpecBuilder, VarSetter
from puzzlespec.libs import std, optional as opt

# Spec Builder
p: PuzzleSpecBuilder = PuzzleSpecBuilder()

####################################
# Define Parameters as *Variables* #
####################################
# Grid dim as N x N
N = var(Int, name='N')

# Box size as sqrt(N)
box_size = var(Int, name='box_size')

# Constraints on parameters (N must be a perfect square)
p += [box_size*box_size == N, box_size >= 0]

##############################
# Domains are typed *values* #
##############################

# Domain for decision variables
Digits = std.range(1, N) # [1..N)

# Grid structure: Domain of Cell indices
Cells = fin(N)*fin(N)

#############################
# Supports refinement types # 
#############################
# Alternate definition of box_size:  {i: Int | i >=0 & i*i==N}
refinement_dom = U(Int).restrict(lambda i: (i >= 0) & (i*i==N))
box_size_alt = var(dom=refinement_dom)

#########################
# Functions are *total* #
#########################
# variables can be functions
cell_digits = func_var(dom=Cells, codom=Digits, name="cell_digits")

##############################
# Quantifcation over domains #
##############################
# Row constraint (numpy-style syntax)
p += fin(N).forall(lambda r: std.distinct(cell_digits[Cells[r,:]]))

# Alternate syntax
p += cell_digits.cols().forall(lambda col_vals: std.distinct(col_vals))

# Box constraint
p += cell_digits.tiles(
    #size=[box_size, box_size],
    size=[3,3],
    #stride=[box_size, box_size]
    stride=[3,3]
).forall(lambda box_vals: std.distinct(box_vals))

#####################
# Clues as Sum Type #
#####################
OptionalDigits = U(Unit) + Digits # Dom[𝟙] ⊎ Digits 
givens = func_var(dom=Cells, codom=OptionalDigits, name="givens")

# Given vals must be consistent with cell_digits
p += Cells.forall(
    lambda c: givens(c).match(                # pattern match for clue
        lambda _: True,                       # True if Unit
        lambda v: cell_digits(c)==v # Same as cell_digit if given
    )
)

spec = p.build("Sudoku")
print("UNOPTIMIZED SPEC")
print(spec)
input()
print("OPTIMIZED SPEC")
print(spec.optimize())
input()
print("SETTING N=9")
setter = VarSetter(spec)
setter.N=9
setter.box_size=3
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
