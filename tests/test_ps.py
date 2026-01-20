from puzzlespec import make_enum, var, func_var, Unit, Int, U, PuzzleSpecBuilder, VarSetter
from puzzlespec.libs import std
from puzzlespec.libs import optional as opt, topology as topo, nd
fin = nd.fin
def test_basic():
    f = nd.fin(5)
    g = nd.fin(5)*nd.fin(3)
    h = g.map(lambda i, j: i+j)
    print(h)
    print(h.simplify)

#test_basic()

def test_vars():
    n = var(Int, name='n')
    #m = var(fin(n), name='m')
    m = var(Int, name='m')
    f0 = func_var(fin(n), fin(m), name='f0')
    print(f0.T)
    print(f0.T.simplify)
    f1 = func_var(fin(n), lambda i: fin(m+i), name='f1')
    print(f1.T.simplify)
    f2 = func_var(fin(n), lambda i: fin(m+i), lambda i, j: fin(i+j) + fin(j), name='f2')
    print(f2.T.simplify)
    print(f2(3)(4).T.simplify)
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
        print(v0.simplify)
        v1 = f[3:5]
        print(v1.simplify)
        wins = f.windows(3, 3)
        print(wins.simplify)
        win1 = wins[n]
        print(win1.simplify)
        g = f.map(lambda i: i*i)
        print(g.simplify)
        g0 = g[n:n+3][2]
        print(g0.simplify)

#test_1d()

def test_nd():
    n = var(Int, name='n')
    m = var(Int, name='m')
    d = nd.fin(n) * nd.fin(m)
    g = d[2:5, 3]
    print(g)
    print(g.simplify)
    rows = nd.rows(d)
    print(rows.simplify)
    row5 = rows[5]
    print(row5)
    print(row5.simplify)
    tiles = nd.tiles(d, (2,2), (2,2))
    print(tiles)
    print(tiles.simplify)
    f = d.map(lambda i, j: i*2+j, _inj=True)
    print(f)
    print(f.simplify)
    print(f[1,2].simplify)
    rows = nd.rows(f)
    print(rows)
    print("*"*30)
    print(rows.simplify)
    tiles = nd.tiles(f, (2,2), (2,2))
    print(tiles)
    a = tiles.forall(lambda vals: std.distinct(vals))
    print(a.simplify)

test_nd()

def test_nd_vars():
    n = var(Int, name='n')
    #m = var(nd.fin(n).unwrap(), name='m')
    #print(m.simplify)
    #f0 = func_var(nd.fin(n), lambda i: nd.fin(m)[i[0]:3], name='f0')
    #f0 = func_var(nd.fin(n).unwrap(), nd.fin(m).unwrap(), name='f0')
    #f0 = func_var(nd.fin(n)*nd.fin(n), nd.fin(m), Int, name='f0')
    f0 = func_var(nd.fin(n)*nd.fin(8), Int, name='f0')
    #print(f0[2,3].simplify)
    rows = nd.rows(f0)
    print(rows.type_check())
    print("*"*30)
    print(rows)
    print("*"*30)
    rs = rows.simplify
    print(rs)
    print(rs.type_check())
    assert 0
    #print(rows.T)
    b = rows.forall(lambda v: std.distinct(v))
    print("*"*30)
    print(b)
    print("*"*30)
    print(b.simplify)

#test_nd_vars()


def test_empty_func():
    func = fin(5).empty_func()
    for i in fin(5):
        func[i] = i+1
    print(func)
    print(type(func))
    print(func[3:7])


def test_grid():
    # Can construct finite domains
    fin5 = ps.fin(5)
    fin6 = ps.fin(6)
    print(fin5)

    # Domains are first class terms and have operators

    # cartesian product
    print(fin5 * fin6)

    # Disjoint union 
    print(fin5 + fin6)

    # domains have a 'DomainType'
    print((fin5 + fin6).T)

    # Create variables
    nR = ps.var(sort=ps.Int, name='nR')
    # Can use domain refinement for variables
    nC = ps.var(dom=fin5, name='nC')
    finR = ps.fin(nR)
    finC = ps.fin(nC)
    # Can define domains in terms of variables
    cells = ps.fin(nR) * ps.fin(nC)
    print(cells[2,1:])
    print(cells[2,1:].simplify)

    # can define quantified constraints over domains
    e_con = finR.exists(lambda i: i % 2 == 3)
    print(e_con)

    ## Funcs
    # Can create a total function Dom -> expr
    func = finR.map(lambda i: ps.fin(i))
    func2 = func.map(lambda dom: dom.map(lambda i: i%nC))
    val = func2(1)(2)
    print(func)
    print(func2)
    print(val)
    # Can do arbitrarily nested quanitification
    func_con = func.forall(lambda dom: dom.forall(lambda i: i < nC))
    print(func_con)
    print(func_con.simplify)
    refv = ps.var(dom=finR, name='refv')
    print(refv.T)

    refv2 = finR.map(lambda i: ps.var(dom=ps.fin(finC[i]), indices=(i,), name='refv2'))
    print(refv2.T)
    print(refv2)
    cells = ps.fin(nR) * ps.fin(nC)
    print(cells[1,2].simplify)
    print(cells[1,2:])
    print(cells[1,2:].simplify)

    a = ps.func_var(dom=ps.fin(3), codom=ps.fin(4), name='V')
    print(a)
    e = a.forall(lambda i: i==2)
    print(e)
    print(e.simplify)


    print("+"*50)
    print(cells.rows()[3:])
    print(cells.rows()[:8][2:3].simplify)
    print(finR.windows(2))
    print(finR.windows(2).simplify)
    print(cells.tiles((2,3), (4,5)))
    print(cells.tiles((2,3), (4,5)).simplify)
    #spec = ps.PuzzleSpecBuilder()
    #
    ## Can add constraints to the spec
    #spec += [nR % 2 == 0, nC % 2 == 0, nR > 3, nC > 3]
    #
    ## can print rules
    #print(spec.constraints)

