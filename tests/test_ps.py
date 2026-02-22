from puzzlespec import make_enum, var, func_var, Unit, Int, U, PuzzleSpecBuilder, VarSetter
from puzzlespec.libs import std
from puzzlespec.libs import optional as opt, topology as topo, nd
from puzzlespec.compiler.passes.analyses.nd_info import get_dom_info
fin = std.fin
def test_basic():
    f = std.fin(5)
    print(f)
    g = std.fin(5)*nd.fin(3)
    h = g.map(lambda i, j: i+j, inj=True)
    print(h)
    print(h.simplify())
    img = h.image
    print(img[2,3].simplify())

test_basic()

def test_vars():
    n = var(Int, name='n')
    #m = var(fin(n), name='m')
    m = var(Int, name='m')
    f0 = func_var(fin(n), fin(m), name='f0')
    print(f0.T)
    print(f0.T.simplify())
    f1 = func_var(fin(n), lambda i: fin(m+i), name='f1')
    print(f1.T.simplify())
    f2 = func_var(fin(n), lambda i: fin(m+i), lambda i, j: fin(i+j) + fin(j), name='f2')
    print(f2.T.simplify())
    print(f2(3)(4).T.simplify())
    print(f2(m)(n).T._rawT)

#test_vars()

def test_1d():
    n = var(Int, name='n')
    f1 = fin(n)
    f2 = nd.range(2, n)
    for f in (f1, f2):
        print("*"*20)
        print(f)
        v0 = f[3]
        print(v0.simplify())
        v1 = f[3:5]
        print(v1.simplify())
        wins = f.windows(3, 3)
        print(wins.simplify())
        win1 = wins[n]
        print(win1.simplify())
        g = f.map(lambda i: i*i)
        print(g.simplify())
        g0 = g[n:n+3][2]
        print(g0.simplify())

#test_1d()

def test_nd():
    n = var(Int, name='n')
    m = var(Int, name='m')
    d = std.fin(n) * nd.fin(m)
    g = d[2:5, 3]
    print(g)
    print(g.simplify())
    rows = nd.rows(d)
    print(rows.simplify())
    row5 = rows[5]
    print(row5)
    print(row5.simplify())
    f = d.map(lambda i,j: i+j)
    tiles = nd.tiles(d, (2,2), (2,2))
    print("Tiles")
    print(tiles)
    tiles.type_check()
    print(tiles.simplify())
    f = d.map(lambda i, j: i*2+j, inj=True)
    print(f)
    print(f.simplify())
    print(f[1,2].simplify())
    rows = nd.rows(f)
    print(rows)
    print("*"*30)
    print(rows.simplify())
    tiles = nd.tiles(f, (2,2), (2,2))
    print(tiles)
    a = tiles.forall(lambda vals: std.distinct(vals))
    print(a.simplify())

#test_nd()

def test_nd_vars():
    n = var(Int, name='n')
    #m = var(std.fin(n).unwrap(), name='m')
    #print(m.simplify())
    #f0 = func_var(std.fin(n), lambda i: nd.fin(m)[i[0]:3], name='f0')
    #f0 = func_var(std.fin(n).unwrap(), nd.fin(m).unwrap(), name='f0')
    #f0 = func_var(std.fin(n)*nd.fin(n), nd.fin(m), Int, name='f0')
    f0 = func_var(std.fin(n)*nd.fin(8), Int, name='f0')
    #print(f0[2,3].simplify())
    rows = nd.rows(f0)
    print(rows.type_check())
    print("*"*30)
    print(rows)
    print("*"*30)
    rs = rows.simplify()
    print(rs)
    print(rs.type_check())
    assert 0
    #print(rows.T)
    b = rows.forall(lambda v: std.distinct(v))
    print("*"*30)
    print(b)
    print("*"*30)
    print(b.simplify())

#test_nd_vars()


def test_empty_func():
    func = fin(5).empty_func()
    for i in fin(5):
        func[i] = i+1
    print(func)
    print(type(func))
    print(func[3:7])

def test_singleton():
    print(get_dom_info(std.fin(4).node))
    F = std.fin(5).map(lambda v: v.singleton)
    p = get_dom_info(F(3).node)
    print(p)
    prod = std.fin(5)*nd.fin(2).singleton
    p = get_dom_info(prod.node)
    print(p)


#test_singleton()