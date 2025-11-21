from __future__ import annotations

from ..pass_base import Transform, Context, handles
from ...dsl import ir
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
    
    # Higher order ops
    #@handles(ir.SumReduce)
    #def _(self, node: ir.SumReduce) -> ir.Node:
    #    lst, = self.visit_children(node)
    #    match (lst):
    #        case ir.List(elems):
    #            if all(isinstance(e, ir.Lit) for e in elems):
    #                vals = [e.val for e in elems]
    #                return ir.Lit(self._variadic_ops[ir.Sum](*vals), irT.Int)
    #    return node

    #@handles(ir.ProdReduce)
    #def _(self, node: ir.ProdReduce) -> ir.Node:
    #    lst, = self.visit_children(node)
    #    match (lst):
    #        case ir.List(elems):
    #            if all(isinstance(e, ir.Lit) for e in elems):
    #                vals = [e.val for e in elems]
    #                return ir.Lit(self._variadic_ops[ir.Prod](*vals), irT.Int)
    #    return node.replace(lst)

    #@handles(ir.AllDistinct)
    #def _(self, node: ir.AllDistinct) -> ir.Node:
    #    lst, = self.visit_children(node)
    #    match (lst):
    #        case ir.List(elems):
    #            if all(isinstance(e, ir.Lit) for e in elems):
    #                vals = [e.val for e in elems]
    #                distinct = len(set(vals)) == len(vals)
    #                return ir.Lit(distinct, irT.Bool)
    #    return node.replace(lst)