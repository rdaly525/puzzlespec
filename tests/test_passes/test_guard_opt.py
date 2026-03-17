"""GuardStrip: removes all obligations. GuardOpt: removes trivially-true ones.
GuardLift: lifts obligations out of lambdas when independent of bound vars."""
from puzzlespec import Int, Bool, var
from puzzlespec.compiler.dsl import ir, ast
from puzzlespec.compiler.passes.transforms.guard_opt import GuardStrip, GuardOpt, GuardLift
from puzzlespec.libs import std
from .conftest import run_transform


def test_strip_removes_obl():
    # guard(x, True) => x with no obl
    x = var(Int, name='x')
    guarded = x.guard(ast.BoolExpr.make(True))
    assert guarded.node.obl is not None
    result = run_transform(GuardStrip, guarded.node)
    assert result.obl is None


def test_strip_deep():
    # Obligations stripped from nested structure
    x = var(Int, name='x')
    guarded = (x + 1).guard(ast.BoolExpr.make(True))
    result = run_transform(GuardStrip, guarded.node)
    assert result.obl is None


def test_opt_removes_true():
    # obl=Lit(True) is removed
    x = var(Int, name='x')
    guarded = x.guard(ast.BoolExpr.make(True))
    result = run_transform(GuardOpt, guarded.node)
    assert result.obl is None


def test_opt_keeps_nontrivial():
    # obl=p (symbolic) is kept
    p = var(Bool, name='p')
    x = var(Int, name='x')
    guarded = x.guard(p)
    result = run_transform(GuardOpt, guarded.node)
    assert result.obl is not None
