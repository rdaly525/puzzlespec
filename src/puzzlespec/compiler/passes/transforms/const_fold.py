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

    def __init__(self, max_dom_size=100):
        self.max_dom_size=max_dom_size

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
        # Only can simplify if both val and domain are concrete
        # dom_size returns None if domain is not concrete
        if utils._is_concrete(val):
            dom_size = utils._dom_size(domain)
            if dom_size is not None and dom_size <= self.max_dom_size:
                for v in utils._iterate(domain):
                    assert v is not None
                    if v.eq(val):
                        return ir.Lit(ir.BoolT(), val=True)
                return ir.Lit(ir.BoolT(), val=False)
        return node.replace(T, domain, val)
        
    @handles(ir.Forall)
    def _(self, node: ir.Forall):
        T, func = self.visit_children(node)
        # Extract domain and lambda from func if it's a Map
        if isinstance(func, ir.FuncLit):
            _, dom, *vals = func._children
            dom_size = utils._dom_size(dom)
            if dom_size is not None and dom_size <= self.max_dom_size:
                conj_vals = []
                for v in utils._iterate(dom):
                    assert v is not None
                    i = func.layout.index(v)
                    assert i is not None and 0 <= i < len(vals)
                    conj_vals.append(vals[i])
                return ir.Conj(T, *conj_vals)

        return node.replace(T, func)

    @handles(ir.Exists)
    def _(self, node: ir.Exists):
        T, func = self.visit_children(node)
        # Extract domain and lambda from func if it's a Map
        if isinstance(func, ir.FuncLit):
            _, dom, *vals = func._children
            disj_vals = []
            for v in utils._iterate(dom):
                assert v is not None
                i = func.layout.index(v)
                assert i is not None and 0 <= i < len(vals)
                disj_vals.append(vals[i])
            return ir.Disj(T, *disj_vals)
        return node.replace(T, func)

    @handles(ir.Restrict)
    def _(self, node: ir.Restrict):
        T, func = self.visit_children(node)
        # Extract domain and predicate values from func if it's a FuncLit
        if isinstance(func, ir.FuncLit):
            _, dom, *vals = func._children
            dom_size = utils._dom_size(dom)
            if dom_size is not None and dom_size <= self.max_dom_size:
                # Early out: check that all predicate values are literals
                if not all(isinstance(v, ir.Lit) for v in vals):
                    return node.replace(T, func)
                restricted_elems = []
                for v in utils._iterate(dom):
                    assert v is not None
                    i = func.layout.index(v)
                    assert i is not None and 0 <= i < len(vals)
                    pred_val = vals[i]
                    # Only include elements where predicate is True
                    if isinstance(pred_val.T, ir.BoolT) and pred_val.val is True:
                        restricted_elems.append(v)
                # Create DomLit with the restricted elements
                return ir.DomLit(T, *restricted_elems)
        return node.replace(T, func)

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