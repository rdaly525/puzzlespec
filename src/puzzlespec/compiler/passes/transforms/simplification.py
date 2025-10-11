from __future__ import annotations
from hmac import new

from ..pass_base import Transform, Context, handles
from ...dsl import ir, ir_types as irT
import typing as tp

class AlgebraicSimplificationPass(Transform):
    """
    - Applies simple identities (e.g., Add 0, Mul 1/0, etc.)
    - Simple var rewrites (x==x => True)
    - Simple boolean simplifications (Not(Not(x)) => x)

    Leaves non-constant structures intact.
    """

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "const_prop"


    # Arithmetic

    # Simple -(-x) => x
    @handles(ir.Neg)
    def _(self, node: ir.Neg) -> ir.Node:
        a, = self.visit_children(node)
        match (a):
            case (ir.Neg(b)):
                return b
        return node.replace(a)

    @handles(ir.Add)
    def _(self, node: ir.Add) -> ir.Node:
        a, b = self.visit_children(node)
        match (a, b):
            case (ir.Lit(0), _):
                return b
            case (_, ir.Lit(0)):
                return a
        return node.replace(a, b)

    @handles(ir.Sub)
    def _(self, node: ir.Sub) -> ir.Node:
        a, b = self.visit_children(node)
        if a==b:
            return ir.Lit(0)
        match (a, b):
            case (ir.Lit(0), _):
                return ir.Neg(b)
            case (_, ir.Lit(0)):
                return a
            case (_, _):
                return node.replace(a, b)

    @handles(ir.Mul)
    def _(self, node: ir.Mul) -> ir.Node:
        a, b = self.visit_children(node)
        match (a, b):
            case (ir.Lit(1), _):
                return a
            case (_, ir.Lit(1)):
                return b
            case (_, _):
                return node.replace(a, b)

    @handles(ir.Div)
    def _(self, node: ir.Div) -> ir.Node:
        a, b = self.visit_children(node)
        if a==b:
            return ir.Lit(1)
        match (a, b):
            case (_, ir.Lit(1)):
                return a
            case (ir.Lit(0), _):
                return ir.Lit(0)
            case (_, _):
                return node.replace(a, b)

    @handles(ir.Mod)
    def _(self, node: ir.Mod) -> ir.Node:
        a, b = self.visit_children(node)
        match (a, b):
            case (_, ir.Lit(1)):
                return ir.Lit(0)
            case (ir.Lit(0), _):
                return ir.Lit(0)
            case (_, _):
                return node.replace(a, b)

    @handles(ir.Eq)
    def _(self, node: ir.Eq) -> ir.Node:
        a, b = self.visit_children(node)
        if a==b:
            return ir.Lit(True)
        return node.replace(a, b)

    # Booleans
    @handles(ir.Not)
    def _(self, node: ir.Not) -> ir.Node:
        a, = self.visit_children(node)
        match (a):
            case (ir.Not(b)):
                return b
        return node.replace(a)

    @handles(ir.And)
    def _(self, node: ir.And) -> ir.Node:
        a, b = self.visit_children(node)
        match (a, b):
            case (ir.Lit(False), _):
                return ir.Lit(False)
            case (_, ir.Lit(False)):
                return ir.Lit(False)
            case (ir.Lit(True), _):
                return a
            case (_, ir.Lit(True)):
                return b
            case (ir.And(c, d), e):
                return ir.Conj(c, d, e)
            case (e, ir.And(c, d)):
                return ir.Conj(c, d, e)
            case (ir.And(c, d), ir.And(e, f)):
                return ir.Conj(c, d, e, f)
            case (ir.Conj(children), e):
                return ir.Conj(*children, e)
            case (e, ir.Conj(children)):
                return ir.Conj(*children, e)
            case (ir.Conj(children), ir.Conj(children2)):
                return ir.Conj(*children, *children2)
        return node.replace(a, b)
    
    @handles(ir.Or)
    def _(self, node: ir.Or) -> ir.Node:
        a, b = self.visit_children(node)
        match (a, b):
            case (ir.Lit(True), _):
                return ir.Lit(True)
            case (_, ir.Lit(True)):
                return ir.Lit(True)
            case (ir.Lit(False), _):
                return b
            case (_, ir.Lit(False)):
                return a
            case (ir.Or(c, d), e):
                return ir.Disj(c, d, e)
            case (e, ir.Or(c, d)):
                return ir.Disj(c, d, e)
            case (ir.Or(c, d), ir.Or(e, f)):
                return ir.Disj(c, d, e, f)
            case (ir.Disj(children), e):
                return ir.Disj(*children, e)
            case (e, ir.Disj(children)):
                return ir.Disj(*children, e)
            case (ir.Disj(children), ir.Disj(children2)):
                return ir.Disj(*children, *children2)
        return node.replace(a, b)

    @handles(ir.Implies)
    def _(self, node: ir.Implies) -> ir.Node:
        a, b = self.visit_children(node)
        match (a, b):
            case (ir.Lit(True), _):
                return b
            case (_, ir.Lit(True)):
                return ir.Lit(True)
            case (_, ir.Lit(False)):
                return ir.Lit(True)
        return node.replace(a, b)

    # Variadic boolean simplifications
    @handles(ir.Conj)
    def _(self, node: ir.Conj) -> ir.Node:
        new_children = self.visit_children(node)
        reduced = []
        for child in new_children:
            match (child):
                case (ir.Lit(True)):
                    continue
                case (ir.Lit(False)):
                    return ir.Lit(False)
                case (ir.Conj(children)):
                    reduced.extend(children)
                case (ir.And(a, b)):
                    reduced.append(a)
                    reduced.append(b)
                case (_):
                    reduced.append(child)
        if len(reduced) == 0:
            return ir.Lit(True)
        if len(reduced) == 1:
            return reduced[0]
        return node.replace(*reduced)

    @handles(ir.Disj)
    def _(self, node: ir.Disj) -> ir.Node:
        new_children = self.visit_children(node)
        reduced = []
        for child in new_children:
            match (child):
                case (ir.Lit(False)):
                    continue
                case (ir.Lit(True)):
                    return ir.Lit(True)
                case (ir.Disj(children)):
                    reduced.extend(children)
                case (ir.Or(a, b)):
                    reduced.append(a)
                    reduced.append(b)
                case (_):
                    reduced.append(child)
        if len(reduced) == 0:
            return ir.Lit(False)
        if len(reduced) == 1:
            return reduced[0]
        return node.replace(*reduced)

    # Structural / collections simplification
    @handles(ir.ListLength)
    def _(self, node: ir.ListLength) -> ir.Node:
        lst, = self.visit_children(node)
        match (lst):
            case ir.List(elems):
                return ir.Lit(len(lst), irT.Int)
            case ir.ListTabulate(size, _):
                return size
        raise ValueError(f"ListLength expects a list, got {type(lst)}")

    @handles(ir.ListGet)
    def _(self, node: ir.ListGet) -> ir.Node:
        raise NotImplementedError("ListGet is not implemented")

    @handles(ir.ListConcat)
    def _(self, node: ir.ListConcat) -> ir.Node:
        raise NotImplementedError("ListConcat is not implemented")

    @handles(ir.DictLength)
    def _(self, node: ir.DictLength) -> ir.Node:
        dct, = self.visit_children(node)
        match (dct):
            case ir.Dict:
                return dct._size()
            case ir.DictTabulate(keys, vals):
                return ir.ListLength(keys)
        raise ValueError(f"DictLength expects a dict, got {type(dct)}")


    @handles(ir.Sum)
    def _(self, node: ir.Sum) -> ir.Node:
        raise NotImplementedError("Sum is not implemented")

    @handles(ir.Distinct)
    def _(self, node: ir.Distinct) -> ir.Node:
        raise NotImplementedError("Distinct is not implemented")