import puzzlespec as ps
from puzzlespec.libs import optional as opt, topology as topo

# Can construct finite domains
fin5 = ps.fin(5)
fin6 = ps.fin(6)
print(fin5)

# Domains are first class terms and have operators

# cross product
f5_x_f6 = fin5 * fin6
print(f5_x_f6)

# Disjoint union 
f5_u_f6 = fin5 + fin6
print(f5_u_f6)

# domains have a 'DomainType'
print(f5_u_f6.T)

# make a spec for a puzzle
# define parameters
nR, nC = ps.var(sort=ps.Int, name='nR'), ps.var(sort=ps.Int, name='nC')

# Can define domains in terms of variables
fin_nR = ps.fin(nR)

# can define quantified constraints over domains
e_con = fin_nR.exists(lambda i: i % 2 == 3)
print(e_con)

## Funcs
# Can create a total function Dom -> expr
func = fin_nR.map(lambda i: ps.fin(i))
func2 = func.map(lambda dom: dom.map(lambda i: i%nC))
print(func)
print(func2)

# Can do arbitrarily nested quanitification
func_con = func.forall(lambda dom: dom.forall(lambda i: i < nC))
print(func_con)

spec = ps.PuzzleSpecBuilder()

# Can add constraints to the spec
spec += [nR % 2 == 0, nC % 2 == 0, nR > 3, nC > 3]

# can print rules
print(spec.constraints)

