from puzzlespec import var, func_var, Unit, Int, U, PuzzleSpecBuilder, VarSetter
from puzzlespec.libs import std, nd, topology as topo, optional as opt

# Spec Builder
p: PuzzleSpecBuilder = PuzzleSpecBuilder()
    
# Structural parameters + constraints
#nR = v.var(name='nR', dom = Int.U.restrict(lambda nR: nR%2==0))
#nC = v.var(name='nC', dom = Int.U.restrict(lambda nC: nC%2==0))

nR = var(std.Nat, name='nR').refine(lambda i: i%2==0)
nC = var(std.Nat, name='nC').refine(lambda i: i%2==0)

grid = topo.Grid2D(nR, nC)

# color domain (black and white)
BW_dom, BW = std.make_enum('BW')

# Generator variables, i.e., the 'clues' of the puzzle
num_clues = var(std.Nat, name='num_clues')
givens = func_var(grid.cells(), opt.optional_dom(BW_dom), name='givens') # Cell -> Optional[BW_enum]

# clue constraints
p += opt.count_some(givens)==num_clues

## Decision variables, i.e., what the end user will solve for
color = func_var(grid.cells(), BW_dom, name='color') # Cell -> BW_enum

### Puzzle Rules
## Handle the givens
p += grid.cells().forall(
    lambda c: opt.fold(givens(c), on_none=True, on_some=lambda v: color(c)==v)
)

### Equal balance of colors in all rows and cols
p += nd.rows(grid.cells()).forall(lambda row: std.count(color[row], lambda v: v==BW.B) == nC // 2)
p += nd.cols(grid.cells()).forall(lambda col: std.count(color[col], lambda v: v==BW.B) == nR // 2)

### no three in a row
p += nd.rows(color).forall(
    lambda row: row.windows(3, 1).forall(
        lambda win: ~std.all_same(win)
    )
)
p += nd.cols(color).forall(
    lambda row: row.windows(3, 1).forall(
        lambda win: ~std.all_same(win)
    )
)

### Each row and each col should be unique
p += std.distinct(nd.rows(color))
p += std.distinct(nd.cols(color))


spec = p.build("Unruly")
#print("UNOPTIMIZED SPEC")
#print(spec)
#input()
#print("OPTIMIZED SPEC")
print(spec.optimize())
#input()
print("SETTING nR,nC=4,4")
setter = VarSetter(spec)
setter.nR = 4
setter.nC = 4
spec44 = setter.build()
print(spec44.optimize())