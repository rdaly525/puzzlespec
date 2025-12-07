import puzzlespec as ps
from puzzlespec.libs import optional as opt, topology as topo

a = ps.func_var(dom=ps.fin(3), codom=ps.fin(4), name='V')
print(a)
e = a.forall(lambda i: i==2)
print(e)
print(e.simplify)





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

