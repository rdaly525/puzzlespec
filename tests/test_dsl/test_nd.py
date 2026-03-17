from puzzlespec import make_enum, var, func_var, param, Unit, Int, U, PuzzleSpecBuilder, VarSetter
from puzzlespec.compiler.dsl.ast import cartprod
from puzzlespec.libs import std
from puzzlespec.libs import optional as opt, topology as topo, nd
from puzzlespec.compiler.dsl import ast, ast_nd

def check(v: ast.Expr):
    if len(v._freevars) != 0:
        print("ERROR")
        print(v)
        print("Has unbound vars:")
        print(v._freevars)
        v._print_ssa()
        raise ValueError()

# Current issues
def test_basic():
    NDDomainExpr = ast_nd.NDDomainExpr
    NDArrayExpr  = ast_nd.NDArrayExpr
    f = nd.fin(5)
    #check(f.simplify())
    assert isinstance(f, NDDomainExpr)
    assert f.rank==1
    g = f.map(lambda i: nd.fin(i))
    g2 = g(2)
    check(g2)
    assert isinstance(g, NDArrayExpr)
    assert isinstance(g[1], NDDomainExpr)
    assert isinstance(g[1:3], NDArrayExpr)
    #check(g)
    img = g.image
    assert isinstance(img, NDDomainExpr)
    assert isinstance(img[1], NDDomainExpr)
    check(img)
    v = img[1].simplify()
    print(v)

test_basic()

def test_vars():
    fin = nd.fin
    n = var(Int, name='n')
    #m = var(fin(n), name='m')
    m = var(Int, name='m')
    f0 = func_var(fin(n), fin(m), name='f0')
    assert isinstance(f0, ast_nd.NDArrayExpr)
    f1 = func_var(fin(n), lambda i: fin(m+i), name='f1')
    f2 = func_var(fin(n), lambda i: fin(m+i), lambda i, j: fin(i+j) + fin(j), name='f2')
    f3 = f2(3)
    assert isinstance(f3, ast_nd.NDArrayExpr)
    assert isinstance(f2(m), ast_nd.NDArrayExpr)

test_vars()

def test_3d():
    fin = nd.fin
    f = cartprod(fin(2), fin(4), fin(3))
    print(f.map(lambda i,j,k: i+j+k)(0,1,2).simplify())
    assert isinstance(f, ast_nd.NDDomainExpr)
    assert f.rank==3
    s = f[:,1,:]
    check(s)
    assert isinstance(s, ast_nd.NDDomainExpr) and s.rank==2
    #print(s.simplify())
    g = s.map(lambda i,j, k: fin(i+j+k))
    assert isinstance(g, ast_nd.NDArrayExpr) and g.rank==2
    check(g)
    img = g.image
    check(img)
    assert isinstance(img, ast_nd.NDDomainExpr) and img.rank==2

test_3d()

def test_windows():
    n = var(Int, name='n')
    f1 = nd.fin(9)
    f2 = nd.range(2, n)
    for f in (
        f1, 
        f2,
    ):
        wins = nd.windows(f, 3, 3)
        check(wins)
        assert isinstance(wins, ast_nd.NDDomainExpr)
        win1 = wins[1]
        check(win1)
        assert isinstance(win1, ast_nd.NDDomainExpr)
        print(win1.simplify())

test_windows()

def test_nd():
    n = var(Int, name='n')
    m = var(Int, name='m')
    d = nd.fin(n) * nd.fin(m)
    print(d._size(False))
    g = d[2:5, 3]
    assert isinstance(g, ast_nd.NDDomainExpr) and g.rank==1
    print(g.simplify())
    rows = nd.rows(d)
    assert isinstance(rows, ast_nd.NDDomainExpr) and rows.rank==1
    row5 = rows[5]
    assert isinstance(row5, ast_nd.NDDomainExpr) and row5.rank==1
    print(row5)
    print(row5.simplify())

    tiles = nd.tiles(d, (2,2), (2,2))
    assert isinstance(tiles, ast_nd.NDDomainExpr) and tiles.rank==2
    tiles11 = tiles[1,1]
    assert isinstance(tiles11, ast_nd.NDDomainExpr) and tiles11.rank==2
    f = d.map(lambda i, j: i*2+j, inj=True)
    assert isinstance(f, ast_nd.NDArrayExpr) and f.rank==2
    rows = nd.rows(f)
    assert isinstance(rows, ast_nd.NDDomainExpr) and rows.rank==1
    row1 = rows[1]
    assert isinstance(row1, ast_nd.NDArrayExpr) and row1.rank==1
    tiles = nd.tiles(f, (2,2), (2,2))
    assert isinstance(tiles, ast_nd.NDDomainExpr) and tiles.rank==2
    tiles11 = tiles[1,1]
    assert isinstance(tiles11, ast_nd.NDArrayExpr) and tiles11.rank==2
    a = tiles.forall(lambda vals: std.distinct(vals))
    print(a._size(True), a._size(False))
    asimp = a.simplify(strip_guards=False)
    print(asimp._size(True), asimp._size(False))
    print(asimp)
#323 27766616
#206 642460
test_nd()

def test_bug():
    B = param(std.Nat, name='B')
    Cells = nd.fin(B*B)*nd.fin(B*B)
    Digits = nd.range(1, 10)
    F = func_var(Cells, Digits)
    assert isinstance(F, ast_nd.NDArrayExpr) and F.rank==2
    tiles = nd.tiles(F, (B,B), (B,B)).simplify()
    #print(tiles)
    pred = tiles.forall(lambda tile: std.distinct(tile))
test_bug()