import puzzlespec as ps
from puzzlespec.libs import optional as opt, topology as topo

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

# Can define domains in terms of variables
fin_nR = ps.fin(nR)
fin_nC = ps.fin(nC)

# can define quantified constraints over domains
e_con = fin_nR.exists(lambda i: i % 2 == 3)
print(e_con)

## Funcs
# Can create a total function Dom -> expr
func = fin_nR.map(lambda i: ps.fin(i))
func2 = func.map(lambda dom: dom.map(lambda i: i%nC))
val = func2(1)(2)
print(func)
print(func2)
print(val)
# Can do arbitrarily nested quanitification
func_con = func.forall(lambda dom: dom.forall(lambda i: i < nC))
print(func_con)

refv = ps.var(dom=fin_nR, name='refv')
print(refv.T)

refv2 = fin_nR.map(lambda i: ps.var(dom=ps.fin(fin_nC[i]), indices=(i,), name='refv2'))
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


#spec = ps.PuzzleSpecBuilder()
#
## Can add constraints to the spec
#spec += [nR % 2 == 0, nC % 2 == 0, nR > 3, nC > 3]
#
## can print rules
#print(spec.constraints)

