from __future__ import annotations
from . import ir
import typing as tp

def _is_type(T: ir.Type) -> bool:
    return isinstance(T, ir.Type)

def _get_T(T: ir.Type) -> ir.Type:
    if not _is_type(T):
        raise ValueError(f"{T} expected to be a Type")
    if isinstance(T, ir.ApplyT):
        return _get_T(T.piT.lam.retT)
    return T

def _is_kind(T: ir.Type, kind: tp.Type[ir.Type]) -> bool:
    return isinstance(_get_T(T), kind)

def _is_same_kind(T1: ir.Type, T2: ir.Type) -> bool:
    return type(_get_T(T1)) is type(_get_T(T2))

def _is_value(V: ir.Value) -> bool:
    return isinstance(V, ir.Value)

def _is_domain(V: ir.Value) -> bool:
    return _is_value(V) and _is_kind(V.T, ir.DomT)

