from __future__ import annotations
from abc import abstractmethod
import typing as tp
from dataclasses import dataclass
class Type_:
    @abstractmethod
    def cast_as(self, val: tp.Any):
        ...

class TopT_:
    def __repr__(self):
        return '⊤'
TopT = TopT_()

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

class EnumT(Type_):
    _cache = {}
    __match_args__ = ("name",)

    def __new__(cls, name: str, *labels: str):
        key = name
        if key not in cls._cache:
            instance = super().__new__(cls)
            instance.name = name
            instance.labels = labels
            cls._cache[key] = instance
        else:
            T = cls._cache[key]
            if T.labels != labels:
                raise ValueError("Cannot construct two different EnumTs with different labels!")
        return cls._cache[key]
    
    def __repr__(self):
        return f"Enum<{self.name}"

    def cast_as(self):
        raise NotImplementedError()


class DomT(Type_):
    _cache = {}
    __match_args__ = ("carT",)
    carT: Type_

    def __new__(cls, carT: Type_):
        assert isinstance(carT, Type_)
        key = carT
        if key not in cls._cache:
            instance = super().__new__(cls)
            instance.carT = carT
            cls._cache[key] = instance
        return cls._cache[key]
    
    def __repr__(self):
        return f"Dom[{self.carT}]"

    def cast_as(self, val):
        raise NotImplementedError("Cannot construct value of DomT")

class TupleT(Type_):
    _cache = {}
    __match_args__ = ("elemTs",)
    elemTs: tp.Tuple[Type_, ...]
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

class SumT(Type_):
    _cache = {}
    __match_args__ = ("elemTs",)
    elemTs: tp.Tuple[Type_, ...]
    def __new__(cls, *elemTs: Type_):
        if len(elemTs)==0:
            raise NotImplementedError("Cannot handle empty sum type")
        assert all(isinstance(T, Type_) for T in elemTs)
        key = tuple(elemTs)
        if key not in cls._cache:
            instance = super().__new__(cls)
            instance.elemTs = key
            cls._cache[key] = instance
        return cls._cache[key]
    
    def __repr__(self):
        return f"{'⊕'.join(repr(t) for t in self.elemTs)}"

    def cast_as(self, val):
        raise NotImplementedError

class ArrowT(Type_):
    _cache = {}
    __match_args__ = ("argT", "resT")
    argT: Type_
    resT: Type_
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

class FuncT(Type_):
    _cache = {}
    __match_args__ = ("domT", "resT")
    domT: DomT
    resT: Type_
    def __new__(cls, domT: DomT, resT: Type_):
        if not isinstance(domT, DomT):
            raise ValueError(f"domT must be a DomT, got {domT}")
        key = (domT, resT)
        if key not in cls._cache:
            instance = super().__new__(cls)
            instance.domT = domT
            instance.resT = resT
            cls._cache[key] = instance
        return cls._cache[key]

    def __repr__(self):
        return f"{repr(self.domT)} -> {repr(self.resT)}"

    def underlyingT(self):
        return ArrowT(self.domT.carT, self.resT)


## Common concrete CellIdx types
#CellIdxT_RC = TupleT(Int, Int)
#CellIdxT_linear = Int