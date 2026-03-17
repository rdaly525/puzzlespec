"""CanonicalizePass: sort commutative/associative ops, flatten nested ones."""
from puzzlespec import Int, var
from puzzlespec.compiler.dsl import ir, ast
from puzzlespec.compiler.passes.transforms.canonicalize import CanonicalizePass
from .conftest import run_transform


def test_sum_sorted():
    # Sum children are sorted by node ordering
    x = var(Int, name='x')
    y = var(Int, name='y')
    node = (x + y).node
    result = run_transform(CanonicalizePass, node)
    assert isinstance(result, ir.Sum)
    children = list(result._children)
    assert children == sorted(children)


def test_sum_flattened():
    # (x + y) + z => Sum(x, y, z) (flattened)
    x = var(Int, name='x')
    y = var(Int, name='y')
    z = var(Int, name='z')
    node = ((x + y) + z).node
    result = run_transform(CanonicalizePass, node)
    assert isinstance(result, ir.Sum)
    assert len(result._children) == 3


def test_prod_sorted():
    x = var(Int, name='x')
    y = var(Int, name='y')
    node = (x * y).node
    result = run_transform(CanonicalizePass, node)
    assert isinstance(result, ir.Prod)
    children = list(result._children)
    assert children == sorted(children)


def test_idempotent():
    # Running canon twice gives same result
    x = var(Int, name='x')
    y = var(Int, name='y')
    z = var(Int, name='z')
    node = ((x + z) + y).node
    r1 = run_transform(CanonicalizePass, node)
    r2 = run_transform(CanonicalizePass, r1)
    assert r1 == r2
