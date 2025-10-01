from packages.tactics import tactic, values, windows, list_of_ints
from packages.tactics import dom, size, the_one, contains, assign, remove
from puzzlespec import ast as S, ir_types as T, ir as IR


def _cells_all():
    # minimal stand-in: just 3 Int params list for construction
    a, b, c = S.IntParam("a"), S.IntParam("b"), S.IntParam("c")
    return list_of_ints(a, b, c)


def test_builder_naked_single_like():
    with tactic("NakedSingle") as t:
        x = t.bind(_cells_all())
        # Use method helpers: x.dom().size() and x.is_singleton(), the_one via dom().the_one()
        t.when(x.is_singleton())
        t.do(assign(x, x.dom().the_one()))
        r = t.build()

    assert r.node.__class__.__name__ == 'TacRule'
    assert len(r.actions.node._children) == 1


def test_builder_windows_unruly_like():
    # Use a list of three cells and get windows of size 3 (just itself)
    C = _cells_all()
    with tactic("NoThreeEliminate") as t:
        W = t.bind(windows(C, size=3, stride=1))
        v0 = S.IntExpr.make(0)
        # Use the only_candidate_is helper
        t.when(W[0].only_candidate_is(v0))
        t.when(W[1].only_candidate_is(v0))
        t.when(contains(dom(W[2]), v0))
        t.do(remove(W[2], values(v0)))
        r = t.build()

    assert r.node.__class__.__name__ == 'TacRule'
    assert len(r.actions.node._children) == 1


