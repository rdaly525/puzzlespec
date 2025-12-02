from __future__ import annotations
from . import ir
import typing as tp
import itertools as it
import functools as ft

def _is_type(T: ir.Type) -> bool:
    return isinstance(T, ir.Type)

def _is_kind(T: ir.Type, kind: tp.Type[ir.Type]) -> bool:
    return isinstance(T, kind)

def _is_same_kind(T1: ir.Type, T2: ir.Type) -> bool:
    return type(T1) is type(T2)

def _is_value(V: ir.Value) -> bool:
    return isinstance(V, ir.Value)

def _is_domain(V: ir.Value) -> bool:
    return _is_value(V) and _is_kind(V.T, ir.DomT)

def _has_bv(bv: ir.BoundVarHOAS, node: ir.Node):
    if node is bv:
        return True
    return any(_has_bv(bv, c) for c in node._children)
    
def _substitute(node: ir.Node, bv: ir.BoundVarHOAS, arg: ir.Value):
    if isinstance(node, ir.PiTHOAS):
        lam_bv, lam_resT = node._children
        if lam_bv is bv:
            raise ValueError(f"Cannot substitute into lambda type {node}")
    if isinstance(node, ir.LambdaHOAS):
        lam_T, lam_bv, lam_body = node._children
        if lam_bv is bv:
            raise ValueError(f"Cannot substitute into lambda placeholder {node}")
    if node is bv:
        return arg
    new_children = [_substitute(c, bv, arg) for c in node._children]
    return node.replace(*new_children)

def _applyT(funcT: ir.FuncT, arg: ir.Value):
    assert isinstance(funcT, ir.FuncT)
    assert isinstance(arg, ir.Value)
    dom, piT = funcT._children
    assert isinstance(piT, ir.PiTHOAS)
    bv, resT = piT._children
    assert not _has_bv(bv, arg)
    new_resT = _substitute(resT, bv, arg)
    return new_resT

# Checks for any bound/free vars
def _is_concrete(node: ir.Node):
    if isinstance(node, (ir.VarRef, ir.BoundVar, ir.VarHOAS, ir.BoundVarHOAS)):
        return False
    return all(_is_concrete(c) for c in node._children)

def _has_freevar(node: ir.Node):
    if isinstance(node, ir.VarRef):
        return True
    return any(_has_freevar(c) for c in node._children)

def _unpack(node: ir.Node):
    if isinstance(node, ir.TupleLit):
        return tuple(_unpack(c) for c in node._children[1:])
    if isinstance(node, ir.Lit):
        return node.val
    raise NotImplementedError(f"Cannot unpack {node}")

def _lit_val(node: ir.Node) -> tp.Optional[int|bool]:
    if isinstance(node, ir.Lit):
        return node.val
    return None

def _dom_size(dom: ir.dom):
    if not _is_domain(dom):
        raise ValueError(f"Expected domain, got {dom}")
    if isinstance(dom, ir.Universe):
        T: ir.DomT = dom.T
        if not T.fin:
            return None
        else:
            carT: ir.Type = T.carT
            if _is_kind(carT, ir.UnitT):
                return 1
            elif _is_kind(carT, ir.EnumT):
                return len(carT.labels)
            else:
                return None
    if isinstance(dom, ir.RestrictEq):
        _, _, v = dom._children
        if _lit_val(v) is not None:
            return 1
        return None
    if isinstance(dom, ir.Fin):
        return _lit_val(dom._children[1])
    if isinstance(dom, ir.Range):
        lo = _lit_val(dom._children[0])
        hi = _lit_val(dom._children[1])
        if lo is None or hi is None:
            return None
        return hi - lo
    if isinstance(dom, ir.CartProd):
        sizes = tuple(_dom_size(c) for c in dom._children[1:])
        if any(s is None for s in sizes):
            return None
        return ft.reduce(lambda a, b: a * b, sizes, 1)
    if isinstance(dom, ir.DisjUnion):
        sizes = tuple(_dom_size(c) for c in dom._children[1:])
        if any(s is None for s in sizes):
            return None
        return sum(sizes)
    if isinstance(dom, ir.DomLit):
        return len(dom._children[1:])
    return None

# Yields doms or None
def _iterate(dom: ir.Value):
    if not _is_domain(dom):
        raise ValueError(f"Expected domain, got {dom}")
    intT = ir.IntT()
    if isinstance(dom, ir.Universe):
        T: ir.DomT = dom.T
        if not T.fin:
            yield None
        else:
            carT: ir.Type = T.carT
            if _is_kind(carT, ir.UnitT):
                yield ir.Unit(carT)
            elif _is_kind(carT, ir.EnumT):
                for label in carT.labels:
                    yield ir.EnumLit(carT, label)
            else:
                yield None
    elif isinstance(dom, ir.RestrictEq):
        _, _, v = dom._children
        if isinstance(v, ir.Lit):
            yield v
        else:
            yield None
    elif isinstance(dom, ir.Fin):
        n = dom._children[1]
        if not isinstance(n, ir.Lit):
            yield None
        for i in range(n.val):
            yield ir.Lit(intT, val=i)
    elif isinstance(dom, ir.Range):
        lo, hi = dom._children[1:]
        if not isinstance(lo, ir.Lit) or not isinstance(hi, ir.Lit):
            yield None
            return
        for i in range(lo.val, hi.val):
            yield ir.Lit(intT, val=i)
    elif isinstance(dom, ir.CartProd):
        doms = dom._children[1:]
        tupT = None
        for vals in it.product(*[_iterate(edom) for edom in doms]):

            if any(v is None for v in vals):
                yield None
                return
            if tupT is None:
                tupT = ir.TupleT(*(v.T for v in vals))
            yield ir.TupleLit(tupT, *vals)
    elif isinstance(dom, ir.DisjUnion):
        doms = dom._children[1:]
        T = dom.T
        for i, edom in enumerate(doms):
            for v in _iterate(edom):
                if v is None:
                    yield None
                    return
                yield ir.Inj(T.carT, v, i)
    elif isinstance(dom, ir.DomLit):
        for elem in dom._children[1:]:
            yield elem
    else:
        yield None

