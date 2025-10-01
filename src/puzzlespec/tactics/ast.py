from __future__ import annotations
import typing as tp
from dataclasses import dataclass

from puzzlespec import ir, ir_types as irT
from puzzlespec.ast import Expr, IntExpr, BoolExpr, ListExpr, GridExpr

from . import ir as tac_ir


# === Facade expressions for tactic IR ===

@dataclass
class TacExpr(Expr):
    pass


class RuleExpr(TacExpr):
    @property
    def params(self) -> 'ParamsExpr':
        return ParamsExpr(tp.cast(ir.Node, self.node._children[0]), self.T)

    @property
    def guard(self) -> BoolExpr:
        return BoolExpr(tp.cast(ir.Node, self.node._children[1]), irT.Bool)

    @property
    def actions(self) -> 'ActionsExpr':
        return ActionsExpr(tp.cast(ir.Node, self.node._children[2]), self.T)


class ParamsExpr(TacExpr):
    def __len__(self) -> int:
        return len(self.node._children)


class ActionsExpr(TacExpr):
    def __len__(self) -> int:
        return len(self.node._children)


class ProgramExpr(TacExpr):
    def __len__(self) -> int:
        return len(self.node._children)


# --- Constructors ---

def params(*params: Expr) -> ParamsExpr:
    node = tac_ir.TacParams(*[p.node for p in params])
    # params are structural; use Bool type for wrapper neutrality
    return ParamsExpr(node, irT.Bool)


def actions(*actions: TacExpr) -> ActionsExpr:
    node = tac_ir.TacActions(*[a.node for a in actions])
    return ActionsExpr(node, irT.Bool)


def rule(name: str, params_e: ParamsExpr, guard_e: BoolExpr, actions_e: ActionsExpr, explain: tp.Optional[str] = None) -> RuleExpr:
    node = tac_ir.TacRule(params_e.node, guard_e.node, actions_e.node, name=name, explain=explain)
    return RuleExpr(node, irT.Bool)


def program(*rules: RuleExpr) -> ProgramExpr:
    node = tac_ir.TacProgram(*[r.node for r in rules])
    return ProgramExpr(node, irT.Bool)


# --- Domain actions ---

class AssignExpr(TacExpr):
    pass


def assign(target: Expr, value: IntExpr) -> AssignExpr:
    node = tac_ir.TacAssign(target.node, IntExpr.make(value).node)
    return AssignExpr(node, irT.Bool)


class RemoveExpr(TacExpr):
    pass


def remove(target: Expr, values: ListExpr[IntExpr]) -> RemoveExpr:
    node = tac_ir.TacRemove(target.node, values.node)
    return RemoveExpr(node, irT.Bool)


# Canonical primary-view actions (clear naming for primary variable operations)
class PlaceExpr(TacExpr):
    pass


def place(var: Expr, value: IntExpr) -> PlaceExpr:
    node = tac_ir.TacPlace(var.node, IntExpr.make(value).node)
    return PlaceExpr(node, irT.Bool)


class ForbidExpr(TacExpr):
    pass


def forbid(var: Expr, values: ListExpr[IntExpr]) -> ForbidExpr:
    node = tac_ir.TacForbid(var.node, values.node)
    return ForbidExpr(node, irT.Bool)


# --- Aggregate actions ---

class TightenSumExpr(TacExpr):
    pass


def tighten_sum(domain: ListExpr[IntExpr], lower: IntExpr, upper: IntExpr) -> TightenSumExpr:
    node = tac_ir.TacTightenSum(domain.node, IntExpr.make(lower).node, IntExpr.make(upper).node)
    return TightenSumExpr(node, irT.Bool)


class TightenCountExpr(TacExpr):
    pass


def tighten_count(domain: Expr, values: Expr, lower: IntExpr, upper: IntExpr) -> TightenCountExpr:
    node = tac_ir.TacTightenCount(domain.node, values.node, IntExpr.make(lower).node, IntExpr.make(upper).node)
    return TightenCountExpr(node, irT.Bool)


# --- Queries / Guards (read-only) ---

class DomExpr(ListExpr[IntExpr]):
    def size(self) -> IntExpr:
        return size(self)

    def contains(self, value: IntExpr | int) -> BoolExpr:
        return contains(self, IntExpr.make(value))

    def the_one(self) -> IntExpr:
        return the_one(self)


def dom(var: Expr) -> DomExpr:
    node = tac_ir.TacDom(var.node)
    return tp.cast(DomExpr, DomExpr(node, irT.ListT(irT.Int)))


def size(list_expr: ListExpr[Expr] | ListExpr[IntExpr]) -> IntExpr:
    # Reuse ListLength over the node
    return IntExpr(ir.ListLength(list_expr.node), irT.Int)


def the_one(list_expr: ListExpr[IntExpr]) -> IntExpr:
    node = ir.OnlyElement(list_expr.node)
    return IntExpr(node, irT.Int)


def contains(list_expr: ListExpr[IntExpr], value: IntExpr) -> BoolExpr:
    node = ir.ListContains(list_expr.node, IntExpr.make(value).node)
    return BoolExpr(node, irT.Bool)


def count_has(vars_list: ListExpr[Expr], values_list: ListExpr[IntExpr]) -> IntExpr:
    node = tac_ir.TacCountHas(vars_list.node, values_list.node)
    return IntExpr(node, irT.Int)


def list_of_ints(*vals: IntExpr | int) -> ListExpr[IntExpr]:
    nodes = [IntExpr.make(v).node for v in vals]
    node = tac_ir.TacListConst(*nodes)
    return tp.cast(ListExpr[IntExpr], ListExpr(node, irT.ListT(irT.Int)))


# Structural helpers to reference Sudoku-like structures using spec IR
def rows_from(grid: GridExpr[Expr]) -> ListExpr[ListExpr[Expr]]:
    return grid.rows()


def cols_from(grid: GridExpr[Expr]) -> ListExpr[ListExpr[Expr]]:
    return grid.cols()


def row_indices(grid: GridExpr[Expr]) -> ListExpr[IntExpr]:
    # 0..nR-1
    n = grid.nR
    return tp.cast(ListExpr[IntExpr], ListExpr(ir.ListTabulate(n.node, ir.Lambda(ir.BoundVar(), ir.BoundVar())), irT.ListT(irT.Int)))


def col_indices(grid: GridExpr[Expr]) -> ListExpr[IntExpr]:
    n = grid.nC
    return tp.cast(ListExpr[IntExpr], ListExpr(ir.ListTabulate(n.node, ir.Lambda(ir.BoundVar(), ir.BoundVar())), irT.ListT(irT.Int)))


def rows_except(rows: ListExpr[ListExpr[Expr]], r1: ListExpr[Expr], r2: ListExpr[Expr]) -> ListExpr[ListExpr[Expr]]:
    # Build a boolean mask using structural equality; here we use TacListEq placeholder
    mask = rows.map(lambda r: BoolExpr(ir.Not(tac_ir.TacListEq(r.node, r1.node)), irT.Bool) &
                              BoolExpr(ir.Not(tac_ir.TacListEq(r.node, r2.node)), irT.Bool))
    return rows.mask(mask)


def foreach(domain: ListExpr[Expr], fn: tp.Callable[[Expr], Expr]) -> Expr:
    # Lift a builder of actions over a domain into a TacForEach node; returns an action expression
    from puzzlespec.ast import make_lambda
    lam = make_lambda(lambda z: fn(z), domain.elem_type)
    return Expr(tac_ir.TacForEach(domain.node, lam.node), irT.Bool)


# Instance helper methods (monkey-patched for ergonomics)

def _expr_dom(self: Expr) -> DomExpr:
    return tp.cast(DomExpr, dom(self))


def _listexpr_size(self: ListExpr[Expr]) -> IntExpr:
    return size(self)


def _listexpr_count_has(self: ListExpr[Expr], vals: ListExpr[IntExpr]) -> IntExpr:
    return count_has(self, vals)


setattr(Expr, "dom", _expr_dom)
setattr(ListExpr, "size", _listexpr_size)
setattr(ListExpr, "count_has", _listexpr_count_has)


# Common guard helpers and methods

def is_singleton(var: Expr) -> BoolExpr:
    return size(dom(var)) == 1


def only_candidate_is(var: Expr, value: IntExpr | int) -> BoolExpr:
    v = IntExpr.make(value)
    return BoolExpr.all_of(is_singleton(var), the_one(dom(var)) == v)


def _expr_is_singleton(self: Expr) -> BoolExpr:
    return is_singleton(self)


def _expr_only_candidate_is(self: Expr, value: IntExpr | int) -> BoolExpr:
    return only_candidate_is(self, value)


setattr(Expr, "is_singleton", _expr_is_singleton)
setattr(Expr, "only_candidate_is", _expr_only_candidate_is)


# Structural equality helpers for generic Expr and lists
def _expr_equals(self: Expr, other: Expr) -> BoolExpr:
    return BoolExpr(ir.Eq(self.node, other.node), irT.Bool)


def lists_equal(a: ListExpr[Expr], b: ListExpr[Expr]) -> BoolExpr:
    return BoolExpr(tac_ir.TacListEq(a.node, b.node), irT.Bool)


def lists_not_equal(a: ListExpr[Expr], b: ListExpr[Expr]) -> BoolExpr:
    return BoolExpr(ir.Not(tac_ir.TacListEq(a.node, b.node)), irT.Bool)


setattr(Expr, "eq", _expr_equals)


