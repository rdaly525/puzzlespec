from puzzlespec import make_enum, fin, var, func_var, Unit, Int, U, PuzzleSpecBuilder, VarSetter
from puzzlespec.libs import std

p: PuzzleSpecBuilder = PuzzleSpecBuilder()
# Puzzles of the following:
# XAXBXCCCXX -> AAA
# DXBAAX-> DD
# CBA -> C
# XXXXDXBXXXXD -> D
max_dim = 30
Color, colors = make_enum('ABCX')
##############
# Raw inputs #
##############
Ni = var(dom=std.range(1, max_dim), name='Ni')
Gi = func_var(dom=fin(Ni), codom=Color, name='Gi')

###############
# Raw outputs #
###############
No = var(dom=std.range(1, max_dim), name='No')
Go = func_var(dom=fin(No), codom=Color, name='Go')

####################
# L1, Input lifted #
####################
# latent parameters
color = var(dom=Color)
n = var(Int)
# isomorphic representation
# True div gives a refined type with embedded true div constraint (consistency)
Vi = Gi.reshape(Ni/Ki, Ki)
p += fin(Ki).forall(lambda k: std.all_same(Vi[:,k]))

#####################
# L2, Output lifted #
#####################
Ko = var(dom=std.range(1,No+1), name='Ko', L=1)
Vo = Go.reshape(No/Ko, Ko)
p += fin(Ko).forall(lambda k: std.all_same(Vo[:,k]))


#######################
# Transition function #
####################### 

# This is the main inference rule
p += (Ni==No)
p += (Ki==Ko)
def lam(ik, vi):
    i, k = ik
    vo = Vo((i, Ki-(k+1)))
    return vi==vo
p += Vi.enumerate().forall(lam)

arc = p.build('arc1d')
print(arc)