from __future__ import annotations

from ..pass_base import Transform, Context, handles
from ...dsl import ir, utils, ast
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
    } 

    _variadic_ops = {
        ir.Conj: lambda *args: all(args),
        ir.Disj: lambda *args: any(args),
        ir.Sum: lambda *args: sum(args),
        ir.Prod: lambda *args: math.prod(args),
    }
    _bool_ops = set([ir.And, ir.Or, ir.Implies, ir.Not, ir.Eq, ir.Gt, ir.GtEq, ir.Lt, ir.LtEq, ir.Conj, ir.Disj])
    _int_ops = set([ir.Add, ir.Sub, ir.Mul, ir.Div, ir.Mod, ir.Neg, ir.Sum, ir.Prod])

    # Binary operations
    @handles(*_binops.keys())
    def _(self, node: ir.Node) -> ir.Node:
        new_children = self.visit_children(node)
        T = new_children[0]
        new_children = new_children[1:]
        if all(isinstance(c, ir.Lit) for c in new_children):
            vals = [c.val for c in new_children]
            new_lit = ir.Lit(T, self._binops[type(node)](*vals))
            return new_lit
        return node.replace(T, *new_children)

    # variadic operations: Fold constants
    @handles(*_variadic_ops.keys())
    def _(self, node: ir.Node) -> ir.Node:
        new_children = self.visit_children(node)
        T = new_children[0]
        new_children = new_children[1:]
        if all(isinstance(c, ir.Lit) for c in new_children):
            vals = [c.val for c in new_children]
            return ir.Lit(T, self._variadic_ops[type(node)](*vals))
        return node.replace(T, *new_children)
    
    @handles(ir.ApplyFunc)
    def _(self, node: ir.ApplyFunc):
        T, func, arg = self.visit_children(node)
        # Index into a ListLit
        if utils._is_concrete(arg):
            if isinstance(func, ir.FuncLit):
                T, dom, *vals = func._children
                idx = func.layout.index(arg)
                assert idx is not None
                assert isinstance(idx, int) and 0 <= idx < len(vals)
                return vals[idx]
        return node.replace(*self.visit_children(node))

    @handles(ir.IsMember)
    def _(self, node: ir.IsMember):
        T, domain, val = self.visit_children(node)
        if isinstance(domain, ir.Universe):
            return ir.Lit(ir.BoolT(), val=True)

        #T, domain, val = self.visit_children(node)
        #if utils._is_concrete(val):
        #    dom_size = utils._dom_size(domain)
        #    if dom_size is not None and dom_size <= self.max_dom_size:
        #        for v in utils._iterate(domain):
        #            assert v is not None
        #            if v.eq(val):
        #                return ir.Lit(ir.BoolT(), val=True)
        #        return ir.Lit(ir.BoolT(), val=False)
        return node.replace(T, domain, val)
        
