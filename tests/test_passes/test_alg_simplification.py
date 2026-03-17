"""AlgebraicSimplificationPass: identity, absorbing, and structural simplifications."""
from puzzlespec import Int, var
from puzzlespec.compiler.dsl import ir, ast
from puzzlespec.compiler.passes.transforms.alg_simplification import AlgebraicSimplificationPass
from .conftest import run_transform


def test_sum_zero():
    # x + 0 => x
    x = var(Int, name='x')
    node = (x + 0).node
    result = run_transform(AlgebraicSimplificationPass, node)
    assert not isinstance(result, ir.Sum)


def test_sum_cancel():
    # x + (-x) => Sum() (empty sum, cancels out)
    x = var(Int, name='x')
    node = (x + (-x)).node
    result = run_transform(AlgebraicSimplificationPass, node)
    assert isinstance(result, ir.Sum) and len(result._children) == 0


def test_prod_one():
    # x * 1 => x
    x = var(Int, name='x')
    node = (x * 1).node
    result = run_transform(AlgebraicSimplificationPass, node)
    assert not isinstance(result, ir.Prod)


def test_prod_zero():
    # x * 0 => 0
    x = var(Int, name='x')
    node = (x * 0).node
    result = run_transform(AlgebraicSimplificationPass, node)
    assert isinstance(result, ir.Lit) and result.val == 0


def test_double_neg():
    # -(-x) => x
    x = var(Int, name='x')
    node = (-(-x)).node
    result = run_transform(AlgebraicSimplificationPass, node)
    assert isinstance(result, ir.VarHOAS)


def test_not_not():
    # not(not(p)) => p
    from puzzlespec import Bool
    p = var(Bool, name='p')
    node = (~(~p)).node
    result = run_transform(AlgebraicSimplificationPass, node)
    assert isinstance(result, ir.VarHOAS)


def test_eq_self():
    # x == x => True
    x = var(Int, name='x')
    node = ir.Eq(ir.BoolT(), x.node, x.node)
    result = run_transform(AlgebraicSimplificationPass, node)
    assert isinstance(result, ir.Lit) and result.val == True


def test_floordiv_by_one():
    # x // 1 => x
    x = var(Int, name='x')
    node = (x // 1).node
    result = run_transform(AlgebraicSimplificationPass, node)
    assert not isinstance(result, ir.FloorDiv)


def test_implies_true_antecedent():
    # True => p  simplifies to p
    from puzzlespec import Bool
    p = var(Bool, name='p')
    node = ast.BoolExpr.make(True).implies(p).node
    result = run_transform(AlgebraicSimplificationPass, node)
    assert isinstance(result, ir.VarHOAS)


def test_proj_tuple():
    # proj_0((a, b)) => a
    x = var(Int, name='x')
    y = var(Int, name='y')
    tup = ast.TupleExpr.make((x, y))
    node = tup[0].node
    result = run_transform(AlgebraicSimplificationPass, node)
    assert isinstance(result, ir.VarHOAS)
