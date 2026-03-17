from __future__ import annotations
from . import ir
import typing as tp
import itertools as it
import functools as ft

def _is_type(T: ir.Type) -> bool:
    return isinstance(T, ir.Type)

def _unrwap_ref(T: ir.Type) -> ir.Type:
    return T.rawT

def _is_kind(T: ir.Type, kind: tp.Type[ir.Type]) -> bool:
    return isinstance(T.rawT, kind)

def _is_same_kind(T1: ir.Type, T2: ir.Type) -> bool:
    if not _is_type(T1) or not _is_type(T2):
        raise TypeError(f"Cannot compare types {T1} and {T2}")
    assert _is_type(T1) and _is_type(T2)
    return T1.rawT == T2.rawT

def _is_value(V: ir.Value) -> bool:
    return isinstance(V, (ir.Value, ir.BoundVar, ir.BoundVarHOAS))

def _is_domain(V: ir.Value) -> bool:
    return _is_value(V) and _is_kind(V.T, ir.DomT)

def _has_bv(bv: ir.BoundVarHOAS, node: ir.Node):
    if node is bv:
        return True
    return any(_has_bv(bv, c) for c in node.all_nodes)
    
def _get_bvs(node: ir.Node) -> set[ir.BoundVarHOAS]:
    if isinstance(node, ir.BoundVarHOAS):
        return set((node,))
    if not node.all_nodes:
        return set()
    return set.union(*(_get_bvs(c) for c in node.all_nodes))

def substitute(node: ir.Node, bv: ir.BoundVarHOAS, arg: ir.Value):
    cache = {bv: arg}
    ret = _substitute(node, cache)
    del cache
    return ret
#def _substitute(node: ir.Node, bv: ir.BoundVarHOAS, arg: ir.Value, cache: tp.Mapping[ir.Node, ir.Node]):
def _substitute(node: ir.Node, cache: tp.Mapping[ir.Node, ir.Node]):
    #if isinstance(node, ir.LambdaTHOAS):
    #    lam_bv, lam_resT = node.children
    #    if lam_bv == bv:
    #        raise ValueError(f"Cannot substitute into lambda type {node}")
    #if isinstance(node, ir.LambdaHOAS):
    #    lam_T, lam_bv, lam_body = node.children
    #    if lam_bv == bv:
    #        raise ValueError(f"Cannot substitute into lambda placeholder {node}")
    if node in cache:
        return cache[node]
    new_children = tuple(_substitute(c, cache) for c in node.children)
    if isinstance(node, ir.Value):
        new_T = _substitute(node.T, cache)
        new_obl = _substitute(node.obl, cache) if node.obl is not None else None
        new_node = node.replace(*new_children, T=new_T, obl=new_obl)
    elif isinstance(node, ir.Type):
        new_ref = _substitute(node.ref, cache) if node.ref is not None else None
        new_view = _substitute(node.view, cache) if node.view is not None else None
        new_obl = _substitute(node.obl, cache) if node.obl is not None else None
        new_node = node.replace(*new_children, ref=new_ref, view=new_view, obl=new_obl)
    else:
        new_node = node.replace(*new_children)
    cache[node] = new_node
    return new_node

#def _applyT(lamT: ir.LambdaT, arg: ir.Value):
#    assert isinstance(arg, ir.Value)
#    assert isinstance(lamT, ir.LambdaTHOAS)
#    bv, resT = lamT.children
#    #print(f"Applying {arg} to {lamT}")
#    if bv is arg:
#        return resT
#    new_resT = _substitute(resT, bv, arg)
#    return new_resT

# Checks for any bound/free vars
def _is_concrete(node: ir.Node):
    if isinstance(node, (ir.VarRef, ir.BoundVar, ir.VarHOAS, ir.BoundVarHOAS)):
        return False
    return all(_is_concrete(c) for c in node.all_nodes)

def _has_freevar(node: ir.Node):
    if isinstance(node, ir.VarRef):
        return True
    return any(_has_freevar(c) for c in node.all_nodes)

def _unpack(node: ir.Node):
    if isinstance(node, ir.TupleLit):
        return tuple(_unpack(c) for c in node.children)
    if isinstance(node, ir.Lit):
        return node.val
    raise NotImplementedError(f"Cannot unpack {node}")

def _lit_val(node: ir.Node) -> tp.Optional[int|bool]:
    if isinstance(node, ir.Lit):
        return node.val
    return None