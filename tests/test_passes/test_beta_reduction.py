"""BetaReductionHOAS: substitute argument into lambda body at application sites."""
from puzzlespec import Int, var
from puzzlespec.compiler.dsl import ir, ast
from puzzlespec.compiler.passes.transforms.beta_reduction import BetaReductionHOAS
from puzzlespec.libs import nd
from .conftest import run_transform


def _all_nodes(node):
    yield node
    if hasattr(node, 'all_nodes'):
        for c in node.all_nodes:
            yield from _all_nodes(c)


def test_simple_apply():
    # (lambda i. i+1)(3) => 3+1
    lam = nd.fin(5).map(lambda i: i + 1).node
    app = ir.Apply(ir.IntT(), lam, ir.Lit(ir.IntT(), val=3))
    result = run_transform(BetaReductionHOAS, app)
    # BoundVarHOAS should be gone — substituted with Lit(3)
    assert not any(isinstance(n, ir.BoundVarHOAS) for n in _all_nodes(result))
    assert not isinstance(result, ir.Apply)


def test_identity():
    # (lambda i. i)(3) => 3
    lam = nd.fin(5).map(lambda i: i).node
    app = ir.Apply(ir.IntT(), lam, ir.Lit(ir.IntT(), val=3))
    result = run_transform(BetaReductionHOAS, app)
    assert isinstance(result, ir.Lit) and result.val == 3


def test_no_reduce_standalone():
    # lambda alone is not reduced
    lam = nd.fin(5).map(lambda i: i + 1).node
    result = run_transform(BetaReductionHOAS, lam)
    assert isinstance(result, ir.LambdaHOAS)
