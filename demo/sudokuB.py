from puzzlespec import var, func_var, param, func_param, cartprod, Unit, Int, U, PuzzleSpecBuilder, VarSetter
from puzzlespec.libs import std, nd

# Spec Builder
p: PuzzleSpecBuilder = PuzzleSpecBuilder()

####################################
# Define Parameters as *Variables* #
####################################
# Grid dim as N x N
B = param(std.Nat, name='B')
N = B*B

##############################
# Domains are typed *values* #
##############################

# Grid structure: Domain of Cell indices
Cells = nd.fin(N) * nd.fin(N)

# Domain for decision variables
Digits = nd.range(1, N+1) # [1..N)

#########################
# Functions are *total* #
#########################
# variables can be functions.
cell_digits = func_var(Cells, Digits, name="cell_digits") # Cells -> Digits

##############################
# Quantifcation over domains #
##############################

# Alternate syntax
Units = dom_lit
p += nd.rows(cell_digits).forall(lambda row_vals: std.distinct(row_vals))
p += nd.cols(cell_digits).forall(lambda col_vals: std.distinct(col_vals))

# Box constraint
p += nd.tiles(
    cell_digits,
    size=(B, B),
    stride=(B, B)
).forall(lambda box_vals: std.distinct(box_vals))

#####################
# Clues as Sum Type #
#####################
OptionalDigits = U(Unit) + Digits # Dom[𝟙] ⊎ Digits 
givens = func_param(Cells, OptionalDigits, name="givens")

# Given vals must be consistent with cell_digits
p += Cells.forall(
    lambda c: givens(c).match(      # pattern match for clue
        lambda _: True,             # True if Unit
        lambda d: cell_digits(c)==d # Same as cell_digit if given
    )
)

spec = p.build("Sudoku")
print(spec.optimize())
exit()
#print("SETTING B = 3")
#setter = VarSetter(spec)
#setter.B = 3
#spec3 = setter.build()
#print(spec3.optimize())
