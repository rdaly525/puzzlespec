from puzzlespec import make_enum, var, func_var, Unit, Int, U, PuzzleSpecBuilder, VarSetter
from puzzlespec.libs import std
from puzzlespec.libs import optional as opt, topology as topo, nd
from puzzlespec.compiler.passes.transforms.add_refinements import free_var_refine, add_refinements
from puzzlespec.compiler.passes.transforms.refine import RefineBottomUp
from puzzlespec.compiler.passes import Context
from puzzlespec.compiler.dsl import ast
fin = nd.fin

def test_guard():
    n5 = var(fin(5), name='n5')
    n6 = var(fin(n5), name='n6')
    a = n5 + n6
    an = a.simplify()
    print(an)

test_guard()

def test_refine():
    n5 = var(fin(5), name='n5')
    n6 = var(fin(n5), name='n6')
    a = n5 + n6
    a = add_refinements(a.node)
    a = free_var_refine(a)
    node = RefineBottomUp()(a, Context)[0]
    a = ast.wrap(a)
    an = ast.wrap(node).simplify()
    print(an.T)

#test_refine()