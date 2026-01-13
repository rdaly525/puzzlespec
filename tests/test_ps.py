from puzzlespec import make_enum, fin, var, func_var, Unit, Int, U, PuzzleSpecBuilder, VarSetter
from puzzlespec.libs import std
from puzzlespec.libs import optional as opt, topology as topo, nd

def test_basic():
    f = fin(5)
    g = fin(5)*fin(3)
    h = g.map(lambda i, j: i+j)
    print(h)
    print(h.simplify)

#test_basic()

def test_vars():
    n = var(Int,name='n')
    m = var(fin(n),name='m')
    print(n)
    print(m)
    f0 = func_var(fin(n), fin(m), name='f0')
    print(f0.T.simplify)
    f1 = func_var(fin(n), lambda i: fin(m+i), name='f1')
    print(f1.T.simplify)
    f2 = func_var(fin(n), lambda i: fin(m+i), lambda i, j: fin(i+j) + fin(j), name='f2')
    print(f2.T.simplify)
    print(f2(m)(n).T)
    print(f2(m)(n).T._rawT)

#test_vars()

def test_nd():
    n = var(Int, name='n')
    #d = nd.range(-3,3) * nd.range(3, n)
    d = nd.fin(n) * nd.fin(6)
    d.type_check()
    print("T1")
    #r = nd.tiles(d, (2,2),(2,2))
    #print(r.simplify)
    #assert 0
    g = d[2:5,3]
    gsimp = g.simplify
    gsimp.type_check()
    print(gsimp.T)
    print("T2")
    #print(d[g].simplify)
    f = d.map(lambda i, j: i*2+j, _inj=True)
    f.type_check()
    print("T3")
    #print(f.T.simplify)
    print("T4")
    #print(f.simplify)
    print("T5")
    print(f.simplify)
    print("T6")
    print(f[1,2].simplify)


#test_nd()

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

test_nd_vars()



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

