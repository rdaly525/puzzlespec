"""DomainSimplificationPass: simplify domain expressions (Card, CartProd, etc.)."""
from puzzlespec import Int, var
from puzzlespec.compiler.dsl import ir, ast
from puzzlespec.compiler.passes.transforms.dom_simplification import DomainSimplificationPass
from puzzlespec.libs import nd
from .conftest import run_transform


def test_card_fin():
    # |Fin(5)| => 5
    d = nd.fin(5)
    node = d.size.node
    result = run_transform(DomainSimplificationPass, node)
    assert isinstance(result, ir.Lit) and result.val == 5


def test_card_singleton():
    # |{x}| => 1
    x = var(Int, name='x')
    domT = ir.DomT(ir.IntT())
    singleton = ir.Singleton(domT, x.node)
    node = ir.Card(ir.IntT(), singleton)
    result = run_transform(DomainSimplificationPass, node)
    assert isinstance(result, ir.Lit) and result.val == 1


def test_unique_singleton():
    # unique({x}) => x
    x = var(Int, name='x')
    domT = ir.DomT(ir.IntT())
    singleton = ir.Singleton(domT, x.node)
    node = ir.Unique(ir.IntT(), singleton)
    result = run_transform(DomainSimplificationPass, node)
    assert isinstance(result, ir.VarHOAS)


def test_card_cartprod():
    # |A x B| => |A| * |B|
    fin3 = ir.Fin(ir.DomT(ir.IntT()), ir.Lit(ir.IntT(), val=3))
    fin4 = ir.Fin(ir.DomT(ir.IntT()), ir.Lit(ir.IntT(), val=4))
    tT = ir.TupleT(ir.IntT(), ir.IntT())
    cart = ir.CartProd(ir.DomT(tT), fin3, fin4)
    node = ir.Card(ir.IntT(), cart)
    result = run_transform(DomainSimplificationPass, node)
    assert isinstance(result, ir.Prod)
