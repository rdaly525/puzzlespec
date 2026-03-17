"""guard() should conjoin with existing obligations, not replace them."""
from puzzlespec import Int, Bool, var
from puzzlespec.compiler.dsl import ir, ast


def test_value_guard_conjoins():
    # guard(guard(x, p), q) should have obl = p & q, not just q
    x = var(Int, name='x')
    p = var(Bool, name='p')
    q = var(Bool, name='q')
    guarded_once = x.guard(p)
    assert guarded_once.obl is not None
    assert guarded_once.obl.node == p.node
    guarded_twice = guarded_once.guard(q)
    obl = guarded_twice.obl
    assert obl is not None
    # Must contain both p and q (as a Conj)
    assert isinstance(obl.node, ir.Conj)
    children = set(obl.node.children)
    assert p.node in children
    assert q.node in children


def test_type_guard_conjoins():
    # guard(guard(T, p), q) should have obl = p & q on the type
    p = var(Bool, name='p')
    q = var(Bool, name='q')
    T = Int.DomT
    guarded_once = T.guard(p)
    assert guarded_once.obl is not None
    assert guarded_once.obl.node == p.node
    guarded_twice = guarded_once.guard(q)
    obl = guarded_twice.obl
    assert obl is not None
    assert isinstance(obl.node, ir.Conj)
    children = set(obl.node.children)
    assert p.node in children
    assert q.node in children


def test_obl_none_unguarded():
    # Unguarded expressions have obl=None
    x = var(Int, name='x')
    assert x.obl is None
    assert Int.DomT.obl is None


def test_single_guard_obl():
    # Single guard sets obl directly
    x = var(Int, name='x')
    p = var(Bool, name='p')
    guarded = x.guard(p)
    assert guarded.obl is not None
    assert guarded.obl.node == p.node
