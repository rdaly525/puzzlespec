from __future__ import annotations

from ..pass_base import Transform, Context, handles
from ...dsl import ir
import typing as tp

class ConstFoldPass(Transform):
    """Constant Folding
    - When all children are literals, fold the node to a literal

    Leaves non-constant structures intact.
    """

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "const_prop"


    _ops = {
        ir.Neg: lambda a: -a,
        ir.Add: lambda a,b: a+b,
        ir.Sub: lambda a,b: a-b,
        ir.Mul: lambda a,b: a*b,
        ir.Div: lambda a,b: a//b,
        ir.Mod: lambda a,b: a%b,
        ir.Gt: lambda a,b: a>b,
        ir.GtEq: lambda a,b: a>=b,
        ir.Lt: lambda a,b: a<b,
        ir.LtEq: lambda a,b: a<=b,
        ir.Eq: lambda a,b: a==b,
        ir.Not: lambda a: not a,
        ir.And: lambda a,b: a and b,
        ir.Or: lambda a,b: a or b,
        ir.Implies: lambda a,b: (not a) or b,
        ir.Conj: lambda *args: all(args),
        ir.Disj: lambda *args: any(args),
    }    

    # Basic Ops
    @handles(*_ops.keys())
    def _(self, node: ir.Node) -> ir.Node:
        new_children = self.visit_children(node)
        if all(isinstance(c, ir.Lit) for c in new_children):
            return ir.Lit(self._ops[type(node)](*new_children))
        return node.replace(*new_children)

    @handles(ir.Sum)
    def _(self, node: ir.Sum) -> ir.Node:
        lst, = self.visit_children(node)
        if isinstance(lst, ir.List) and all(isinstance(e, ir.Lit) for e in lst._children):
            total = sum(int(e.value) for e in lst._children)
            return ir.Lit(total)
        return node.replace(lst)

    @handles(ir.Distinct)
    def _(self, node: ir.Distinct) -> ir.Node:
        lst, = self.visit_children(node)
        if isinstance(lst, ir.List) and all(isinstance(e, ir.Lit) for e in lst._children):
            return ir.Lit(len(set(lst._children)) == len(lst._children))
        return node.replace(lst)

    @handles(ir.GridDims)
    def _(self, node: ir.GridDims) -> ir.Node:
        g, = self.visit_children(node)
        if isinstance(g, ir.Grid):
            return ir.Lit(g.nR)
        return node.replace(g)