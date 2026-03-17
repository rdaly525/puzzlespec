from __future__ import annotations

from ..pass_base import Transform, Context, handles
from ...dsl import ir, utils, ast
from ._obl_utils import _with_obl
import math
import typing as tp

class ConstFoldPass(Transform):
    """Constant Folding
    - When all children are literals, fold the node to a literal

    Leaves non-constant structures intact.
    """

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "const_prop"

    def run(self, root: ir.Node, ctx: Context):
        return self.visit(root)

    _binops = {
        ir.Neg: lambda a: -a,
        ir.Isqrt: lambda a: math.isqrt(a),
        ir.FloorDiv: lambda a,b: a//b,
        ir.Mod: lambda a,b: a%b,
        ir.Lt: lambda a,b: a<b,
        ir.LtEq: lambda a,b: a<=b,
        ir.Eq: lambda a,b: a==b,
        ir.Not: lambda a: not a,
        ir.Implies: lambda a,b: (not a) or b,
    }

    _variadic_ops = {
        ir.Conj: lambda *args: all(args),
        ir.Disj: lambda *args: any(args),
        ir.Sum: lambda *args: sum(args),
        ir.Prod: lambda *args: math.prod(args),
    }
    _bool_ops = set([ir.Implies, ir.Not, ir.Eq, ir.Lt, ir.LtEq, ir.Conj, ir.Disj])
    _int_ops = set([ir.FloorDiv, ir.Mod, ir.Neg, ir.Sum, ir.Prod])

    # Binary operations
    @handles(*_binops.keys())
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        T = vc.T
        children = vc.children
        if all(isinstance(c, ir.Lit) for c in children):
            vals = [c.val for c in children]
            return _with_obl(ir.Lit(T, self._binops[type(node)](*vals)), vc.obl)
        return node.replace(*children, T=T, obl=vc.obl)

    # variadic operations: Fold constants
    @handles(*_variadic_ops.keys())
    def _(self, node: ir.Node) -> ir.Node:
        vc = self.visit_children(node)
        T = vc.T
        children = vc.children
        if all(isinstance(c, ir.Lit) for c in children):
            vals = [c.val for c in children]
            return _with_obl(ir.Lit(T, self._variadic_ops[type(node)](*vals)), vc.obl)
        return node.replace(*children, T=T, obl=vc.obl)

    @handles(ir.IsMember)
    def _(self, node: ir.IsMember):
        vc = self.visit_children(node)
        T = vc.T
        domain, val = vc.children
        if isinstance(domain, ir.Universe):
            return _with_obl(ir.Lit(ir.BoolT(), val=True), vc.obl)
        return node.replace(domain, val, T=T, obl=vc.obl)
