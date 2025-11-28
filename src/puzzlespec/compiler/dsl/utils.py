from __future__ import annotations
from multiprocessing import Value
from . import ir
import typing as tp

def _is_type(T: ir.Type) -> bool:
    return isinstance(T, ir.Type)

#def _get_T(T: ir.Type) -> ir.Type:
#    if not _is_type(T):
#        raise ValueError(f"{T} expected to be a Type")
#    if isinstance(T, ir.ApplyT):
#        piT = _get_T(T.piT)
#        assert isinstance(piT, ir.PiT)
#        return _get_T(piT.lam.resT)
#    return T

def _is_kind(T: ir.Type, kind: tp.Type[ir.Type]) -> bool:
    return isinstance(T, kind)

def _is_same_kind(T1: ir.Type, T2: ir.Type) -> bool:
    return type(T1) is type(T2)

def _is_value(V: ir.Value) -> bool:
    return isinstance(V, ir.Value)

def _is_domain(V: ir.Value) -> bool:
    return _is_value(V) and _is_kind(V.T, ir.DomT)

def _has_bv(bv: ir._BoundVarPlaceholder, node: ir.Node):
    if node is bv:
        return True
    return any(_has_bv(bv, c) for c in node._children)
    
#def _simplify_T(T: ir.Node) -> ir.Type:
#    #return T
#    new_children = [_simplify_T(c) for c in T._children]
#    if isinstance(T, ir.ApplyT):
#        piT, arg = new_children
#        if not isinstance(piT, ir.PiT):
#            return T.replace(*new_children)
#        dom, lamT = piT._children
#        assert isinstance(lamT, ir._LambdaTPlaceholder)
#        bv, resT = lamT._children
#        resT = _simplify_T(resT)
#        if not _has_bv(bv, resT):
#            return resT
#        return ir.ApplyT(
#            ir.PiT(
#                dom,
#                ir._LambdaTPlaceholder(
#                    bv,
#                    resT
#                )
#            ),
#            arg
#        )
#    return T.replace(*new_children)
        
#def _get_subT(T: ir.Type, fn: tp.Callable[[ir.Type], tp.Optional[ir.Type]]) -> ir.Type:
#    def _getT(T: ir.Type) -> ir.Type:
#        # 1) Try to apply the local transformation first
#        maybe_T = fn(T)
#        if maybe_T is not None:
#            return maybe_T
#
#        # 2) If T is a Pi-type, push the transformation into its codomain
#        if isinstance(T, ir.PiT):
#            dom, lamT = T._children
#            if not isinstance(lamT, ir._LambdaTPlaceholder):
#                raise ValueError(f"Expected _LambdaTPlaceholder in PiT, got {lamT!r}")
#            bv, resT = lamT._children
#            return ir.PiT(
#                dom,
#                ir._LambdaTPlaceholder(bv, _getT(resT)),
#            )
#
#        # 3) If T is an application, push the transformation into the function part
#        if isinstance(T, ir.ApplyT):
#            piT, arg = T.piT, T.arg
#            return ir.ApplyT(_getT(piT), arg)
#
#        if isinstance(T, ir.DomTOf):
#            return ir.DomTOf(_getT(T._children[0]))
#
#        # 4) Otherwise, we don't know how to propagate fn through this constructor
#        raise ValueError(f"_get_subT: don't know how to handle type {T!r}")
#
#    subT = _getT(T)
#    subT = _simplify_T(subT)
#    return subT

def _substitute(node: ir.Node, bv: ir._BoundVarPlaceholder, arg: Value):
    if isinstance(node, ir._LambdaTPlaceholder):
        lam_bv, lam_resT = node._children
        if lam_bv is bv:
            raise ValueError(f"Cannot substitute into lambda type {node}")
    if isinstance(node, ir._LambdaPlaceholder):
        lam_T, lam_bv, lam_body = node._children
        if lam_bv is bv:
            raise ValueError(f"Cannot substitute into lambda placeholder {node}")
    if node is bv:
        return arg
    new_children = [_substitute(c, bv, arg) for c in node._children]
    return node.replace(*new_children)

def _applyT(piT: ir.PiT, arg: Value):
    assert isinstance(piT, ir.PiT)
    assert isinstance(arg, ir.Value)
    dom, lamT = piT._children
    assert isinstance(lamT, ir._LambdaTPlaceholder)
    bv, resT = lamT._children
    assert not _has_bv(bv, arg)
    new_resT = _substitute(resT, bv, arg)
    return new_resT