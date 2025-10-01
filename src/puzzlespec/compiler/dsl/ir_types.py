from __future__ import annotations
import typing as tp
from dataclasses import dataclass
class Type_: ...
class BaseType(Type_):
    _pytype = None
    def cast_as(self, val: tp.Any):
        try:
            return self._pytype(val)
        except:
            raise TypeError(f"{val} is not convertable to {self._pytype}")

class _Bool(BaseType):
    _pytype = bool
    def __repr__(self):
        return "Bool"
    
Bool = _Bool()

class _Int(BaseType):
    _pytype = int
    def __repr__(self):
        return "Int"

Int = _Int()

class _CellIdxT(BaseType):
    _pytype = None
    def __repr__(self):
        return "CellIdxT"
CellIdxT = _CellIdxT()

class _VertexIdxT(BaseType):
    _pytype = None
    def __repr__(self):
        return "VertexIdx"
VertexIdxT = _VertexIdxT()

class _EdgeIdxT(BaseType):
    _pytype = None
    def __repr__(self):
        return "EdgeIdx"
EdgeIdxT = _EdgeIdxT()

class GridT(Type_):
    _cache = {}

    def __new__(cls, valueT: Type_, domain: str):
        key = (valueT, domain)
        if key not in cls._cache:
            instance = super().__new__(cls)
            instance.valueT = valueT
            instance.domain = domain
            cls._cache[key] = instance
        return cls._cache[key]

    def __repr__(self):
        return f"GridT({repr(self.valueT)}, {self.domain})"

class TupleT(Type_):
    _cache = {}
    
    def __new__(cls, *elemTs: Type_):
        key = tuple(elemTs)
        if key not in cls._cache:
            instance = super().__new__(cls)
            instance.elemTs = key
            cls._cache[key] = instance
        return cls._cache[key]
    
    def __repr__(self):
        return f"({', '.join(repr(t) for t in self.elemTs)})"

class ListT(Type_):
    _cache = {}
    
    def __new__(cls, elemT: Type_):
        if elemT not in cls._cache:
            instance = super().__new__(cls)
            instance.elemT = elemT
            cls._cache[elemT] = instance
        return cls._cache[elemT]
    
    def __repr__(self):
        return f"[{repr(self.elemT)}]"

class DictT(Type_):
    _cache = {}
    
    def __new__(cls, keyT: Type_, valT: Type_):
        key = (keyT, valT)
        if key not in cls._cache:
            instance = super().__new__(cls)
            instance.keyT = keyT
            instance.valT = valT
            cls._cache[key] = instance
        return cls._cache[key]
    
    def __repr__(self):
        return f"{{{repr(self.keyT)}: {repr(self.valT)}}}"

class ArrowT(Type_):
    _cache = {}
    
    def __new__(cls, argT: Type_, resT: Type_):
        key = (argT, resT)
        if key not in cls._cache:
            instance = super().__new__(cls)
            instance.argT = argT
            instance.resT = resT
            cls._cache[key] = instance
        return cls._cache[key]

    def __repr__(self):
        return f"{repr(self.argT)} -> {repr(self.resT)}"



