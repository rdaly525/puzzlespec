from __future__ import annotations
from . import ir
import typing as tp
import itertools as it
import functools as ft

def _is_type(T: ir.Type) -> bool:
    return isinstance(T, ir.Type)

def _is_kind(T: ir.Type, kind: tp.Type[ir.Type]) -> bool:
    if isinstance(T, ir.RefT):
        return _is_kind(T.T, kind)
    return isinstance(T, kind)

def _is_same_kind(T1: ir.Type, T2: ir.Type) -> bool:
    if not _is_type(T1) or not _is_type(T2):
        raise TypeError(f"Cannot compare types {T1} and {T2}")
    assert _is_type(T1) and _is_type(T2)
    return T1._key == T2._key

def _is_value(V: ir.Value) -> bool:
    return isinstance(V, ir.Value)

def _is_domain(V: ir.Value) -> bool:
    return _is_value(V) and _is_kind(V.T, ir.DomT)

def _has_bv(bv: ir.BoundVarHOAS, node: ir.Node):
    if node is bv:
        return True
    return any(_has_bv(bv, c) for c in node._children)
    
def _get_bvs(node: ir.Node) -> set[ir.BoundVarHOAS]:
    if isinstance(node, ir.BoundVarHOAS):
        return set((node,))
    if len(node._children) == 0:
        return set()
    return set.union(*(_get_bvs(c) for c in node._children))

def _substitute(node: ir.Node, bv: ir.BoundVarHOAS, arg: ir.Value):
    if isinstance(node, ir.LambdaTHOAS):
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

#def _applyT(lamT: ir.LambdaT, arg: ir.Value):
#    assert isinstance(arg, ir.Value)
#    assert isinstance(lamT, ir.LambdaTHOAS)
#    bv, resT = lamT._children
#    #print(f"Applying {arg} to {lamT}")
#    if bv is arg:
#        return resT
#    new_resT = _substitute(resT, bv, arg)
#    return new_resT

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

def simplify(node: ir.Node) -> ir.Node:
    assert 0
    ctx = Context(self.envs_obj)
    analysis_map = {
        TypeMap: KindCheckingPass()
    }

    opt_passes = [
        CanonicalizePass(),
        AlgebraicSimplificationPass(),
        ConstFoldPass(),
        DomainSimplificationPass(),
        RefineSimplify(),
        BetaReductionPass(),
        #CSE(),
    ]

