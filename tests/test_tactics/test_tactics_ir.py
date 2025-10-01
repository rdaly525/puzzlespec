import pytest

from puzzlespec import ast as S
from puzzlespec import ir_types as T

from packages.tactics import (
    params,
    actions,
    rule,
    program,
    assign,
    remove,
    tighten_sum,
    tighten_count,
    dom,
    size,
    the_one,
    contains,
)


def test_construct_simple_rule_assign():
    # spec vars
    x = S.IntParam("x")

    # guard: size(dom(x)) = 1
    guard = (size(dom(x)) == 1)

    # action: assign x := 5
    act = assign(x, 5)

    r = rule("NakedSingle", params(x), guard, actions(act), explain="x has unique candidate")
    prog = program(r)

    assert r.node._fields == ("name", "explain")
    assert len(r.actions.node._children) == 1
    assert len(prog.node._children) == 1


def test_construct_aggregate_actions():
    # list domain and bounds
    v1, v2, v3 = S.IntExpr.make(1), S.IntExpr.make(2), S.IntExpr.make(3)
    lst = S.ListExpr(ir=S.ir.List(v1.node, v2.node, v3.node), T=T.ListT(T.Int)) if False else None

    # build list using facade utilities
    from packages.tactics import list_of_ints
    list_node = list_of_ints(v1, v2, v3)
    list_expr = list_node  # type: ignore

    guard = S.BoolExpr.make(True)
    a1 = tighten_sum(list_expr, 3, 6)
    # For count, reuse list for both domain and values for construction
    a2 = tighten_count(list_expr, list_expr, 1, 2)

    r = rule("AggregateBounds", params(), guard, actions(a1, a2))
    prog = program(r)

    assert len(r.actions.node._children) == 2
    assert len(prog.node._children) == 1


def test_hidden_single_like_guard_builders():
    # list of three variables as placeholders
    a, b, c = S.IntParam("a"), S.IntParam("b"), S.IntParam("c")
    from packages.tactics import list_of_ints
    vars_list = list_of_ints(a, b, c)

    v = S.IntExpr.make(5)
    # guard builders: contains(dom(x), v)
    g = contains(dom(a), v) | contains(dom(b), v) | contains(dom(c), v)
    assert isinstance(g, S.BoolExpr)


