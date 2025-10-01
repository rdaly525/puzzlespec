from __future__ import annotations
import typing as tp

from puzzlespec import ir as IR
from puzzlespec import ir_types as T
from puzzlespec.ast import Expr, BoolExpr, IntExpr, ListExpr, wrap, IntParam

from .ast import (
    rule as make_rule,
    params as make_params,
    actions as make_actions,
)

from .ast import (
    assign,
    remove,
    place,
    forbid,
    tighten_sum,
    tighten_count,
    dom,
    size,
    contains,
    the_one,
    count_has,
    list_of_ints,
    rows_from,
    cols_from,
    rows_except,
    foreach,
)


class _Scope:
    """Placeholder scope for future extensions."""
    pass


class tactic:
    """Context-managed builder for tactics.

    Usage:
        with tactic("Name") as t:
            x = t.bind(domain_expr)
            t.when(size(dom(x)) == 1)
            t.do(assign(x, the_one(dom(x))))
            rule = t.build()
    """

    def __init__(self, name: str, explain: tp.Optional[str] = None):
        self._name = name
        self._explain = explain
        self._guard: BoolExpr = BoolExpr.make(True)
        self._actions: tp.List[Expr] = []
        self._params: tp.List[Expr] = []
        self._counter: int = 0

    # Context manager protocol
    def __enter__(self) -> "tactic":
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    # API
    def bind(self, domain: Expr | ListExpr[Expr] | None = None) -> Expr:
        """Bind a fresh parameter representing an element from a domain.

        If domain is a ListExpr[T], the bound variable has type T.
        If domain is None, default to Int.
        Otherwise, use the domain's type directly.
        """
        name = f"v{self._counter}"
        self._counter += 1
        if isinstance(domain, ListExpr):
            elemT = domain.elem_type
            expr = wrap(IR.Param(name), elemT)
        elif isinstance(domain, Expr):
            expr = wrap(IR.Param(name), domain.T)
        else:
            expr = IntParam(name)
        self._params.append(expr)
        return expr

    # Removed explicit let: use Python assignment for aliasing expressions

    def where(self, pred: BoolExpr) -> "tactic":
        """Structural filter. Currently conjoined into the guard."""
        self._guard = BoolExpr.all_of(self._guard, BoolExpr.make(pred))
        return self

    def when(self, pred: BoolExpr) -> "tactic":
        """State-dependent guard. Conjoined into the guard."""
        self._guard = BoolExpr.all_of(self._guard, BoolExpr.make(pred))
        return self

    def do(self, *acts: Expr) -> "tactic":
        self._actions.extend(acts)
        return self

    def explain(self, text: str) -> "tactic":
        self._explain = text
        return self

    def build(self):
        return make_rule(
            self._name,
            make_params(*self._params),
            self._guard,
            make_actions(*tp.cast(tp.List[Expr], self._actions)),
            explain=self._explain,
        )


# --- Helper sugars (no boilerplate exposed) ---

def values(*vals: tp.Union[int, IntExpr]) -> ListExpr[IntExpr]:
    return list_of_ints(*vals)


def windows(list_expr: ListExpr[Expr], size: tp.Union[int, IntExpr], stride: tp.Union[int, IntExpr] = 1) -> ListExpr[ListExpr[Expr]]:
    size_e = IntExpr.make(size)
    stride_e = IntExpr.make(stride)
    return list_expr.windows(size=size_e, stride=stride_e)  # type: ignore


# Re-export selected guard/query/action helpers for user code convenience
__all__ = [
    "tactic",
    "values",
    "windows",
    # structural helpers (thin wrappers over spec constructs; placeholder-friendly)
    "rows_from",
    "cols_from",
    "rows_except",
    "foreach",
    # queries/guards
    "dom",
    "size",
    "contains",
    "the_one",
    "count_has",
    # actions
    "assign",
    "remove",
    "place",
    "forbid",
    "tighten_sum",
    "tighten_count",
]


