from __future__ import annotations
from multiprocessing import Value
from . import ir
import typing as tp

def _is_type(T: ir.Type) -> bool:
    return isinstance(T, ir.Type)

def _get_T(T: ir.Type) -> ir.Type:
    if not _is_type(T):
        raise ValueError(f"{T} expected to be a Type")
    if isinstance(T, ir.ApplyT):
        piT = _get_T(T.piT)
        assert isinstance(piT, ir.PiT)
        return _get_T(piT.lam.retT)
    return T

def _is_kind(T: ir.Type, kind: tp.Type[ir.Type]) -> bool:
    return isinstance(_get_T(T), kind)

def _is_same_kind(T1: ir.Type, T2: ir.Type) -> bool:
    return type(_get_T(T1)) is type(_get_T(T2))

def _is_value(V: ir.Value) -> bool:
    return isinstance(V, ir.Value)

def _is_domain(V: ir.Value) -> bool:
    return _is_value(V) and _is_kind(V.T, ir.DomT)

def _has_bv(bv: ir._BoundVarPlaceholder, node: ir.Node):
    if node is bv:
        return True
    return any(_has_bv(bv, c) for c in node._children)
    
def _simplify_T(T: ir.Node) -> ir.Type:
    #return T
    new_children = [_simplify_T(c) for c in T._children]
    if isinstance(T, ir.ApplyT):
        piT, arg = new_children
        if not isinstance(piT, ir.PiT):
            return T.replace(*new_children)
        dom, lamT = piT._children
        assert isinstance(lamT, ir._LambdaTPlaceholder)
        bv, resT = lamT._children
        resT = _simplify_T(resT)
        if not _has_bv(bv, resT):
            return resT
        return ir.ApplyT(
            ir.PiT(
                dom,
                ir._LambdaTPlaceholder(
                    bv,
                    resT
                )
            ),
            arg
        )
    return T.replace(*new_children)
        

    

