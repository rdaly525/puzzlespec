from __future__ import annotations
from abc import abstractmethod
import typing as tp
from dataclasses import dataclass
class Type_:
    @abstractmethod
    def cast_as(self, val: tp.Any):
        ...

class _UnitType(Type_):
    def __repr__(self):
        return "𝟙"
UnitType = _UnitType()

class BaseType(Type_):
    _pytype = None
    def cast_as(self, val: tp.Any):
        if self._pytype is None:
            raise ValueError(f"Cannot create a python value from abstract type {self.__class__.__name__}")
        try:
            return self._pytype(val)
        except:
            raise TypeError(f"{val} is not convertable to {self._pytype}")

class _Bool(BaseType):
    _pytype = bool
    def __repr__(self):
        return "𝔹"
    
Bool = _Bool()

class _Int(BaseType):
    _pytype = int
    def __repr__(self):
        return "ℤ"

Int = _Int()

class _CellIdxT(BaseType):
    _pytype = None
    def __repr__(self):
        return "𝒞"
    
CellIdxT = _CellIdxT()

class _VertexIdxT(BaseType):
    _pytype = None
    def __repr__(self):
        return "𝒱"
VertexIdxT = _VertexIdxT()

class _EdgeIdxT(BaseType):
    _pytype = None
    def __repr__(self):
        return "𝓔"
EdgeIdxT = _EdgeIdxT()

class GridT(Type_):
    _cache = {}
    __match_args__ = ("valueT", "domain")

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
    __match_args__ = ("elemTs",)
    
    def __new__(cls, *elemTs: Type_):
        if len(elemTs)==0:
            return UnitType
        assert all(isinstance(T, Type_) for T in elemTs)
        key = tuple(elemTs)
        if key not in cls._cache:
            instance = super().__new__(cls)
            instance.elemTs = key
            cls._cache[key] = instance
        return cls._cache[key]
    
    def __repr__(self):
        return f"{'x'.join(repr(t) for t in self.elemTs)}"

    def cast_as(self, val):
        if isinstance(val, tp.Iterable) and len(val)==len(self.elemTs):
            return tuple(T.cast_as(v) for T, v in zip(self.elemTs, val))

class ListT(Type_):
    _cache = {}
    __match_args__ = ("elemT",)

    def __new__(cls, elemT: Type_):
        assert isinstance(elemT, Type_)
        if elemT not in cls._cache:
            instance = super().__new__(cls)
            instance.elemT = elemT
            cls._cache[elemT] = instance
        return cls._cache[elemT]
    
    def __repr__(self):
        return f"[{repr(self.elemT)}]"

class DictT(Type_):
    _cache = {}
    __match_args__ = ("keyT", "valT")

    def __new__(cls, keyT: Type_, valT: Type_):
        key = (keyT, valT)
        if key not in cls._cache:
            instance = super().__new__(cls)
            instance.keyT = keyT
            instance.valT = valT
            cls._cache[key] = instance
        return cls._cache[key]
    
    def __repr__(self):
        return f"{{{repr(self.keyT)} ↦ {repr(self.valT)}}}"

class ArrowT(Type_):
    _cache = {}
    __match_args__ = ("argT", "resT")

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

# Common concrete CellIdx types
CellIdxT_RC = TupleT(Int, Int)
CellIdxT_linear = Int



