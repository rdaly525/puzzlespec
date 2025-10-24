from multiprocessing import Value
from . import ir, ir_types as irT
from .spec import PuzzleSpec
import typing as tp
import numpy as np


def _make_clue_var(shape: ir.Node, T: irT.Type_):
    match (T):
        case irT.Int | irT.Bool:
            return ClueVarBase(T)
        case irT.DictT(keyT, valT):
            if not keyT in (irT.TupleT(irT.Int, irT.Int), irT.Int):
                raise NotImplementedError(f"Unsupported key type for dict: {keyT}")
            return ClueVarDict(shape, T)

class ClueSetter:
    def __init__(self, spec: PuzzleSpec):
        self._spec = spec
        self._vars = {}
        for sid in spec.sym.get_gen_vars():
            name = spec.sym.get_name(sid)
            T = spec.tenv[sid]
            shape = spec.evaluate(spec.shape_env[sid])
            self._vars[name] = _make_clue_var(shape, T)

    def __getattr__(self, name: str) -> tp.Any:
        if name in self._vars:
            return self._vars[name]
        else:
            raise AttributeError(f"Attribute {name} not found")

    def build(self) -> PuzzleSpec:
        print()
        assert 0
        ... #TODO

class ClueVarBase:
    def __init__(self, T: irT.Type_):
        self.T = T
        self.val = None

    def set(self, val):
        self.val = self.T.cast_as(val)

    def __setitem__(self, key, val):
        if key==():
            self.set(val)
        else:
            raise ValueError(f"Wrong key type for {self.__class__}")

class ClueVarDict:
    def __init__(self, shape: tp.List[tp.Any], T: irT.DictT):
        if not T.keyT in (irT.TupleT(irT.Int, irT.Int), irT.Int):
            raise NotImplementedError(f"Unsupported key type for dict: {T.keyT}")
        # check if shape is a concrete List of concrete elements:
        self.T = T
        self.shape = shape
        self.val = {k: ClueVarBase(self.T.valT) for k in shape}

    def set(self, val: tp.Any):
        if isinstance(val, tp.Dict):
            for k, v in val.items():
                self[k] = v
        elif isinstance(val, np.ndarray):
            for k, v in np.ndenumerate(val):
                self[k] = v
        else:
            raise ValueError(f"Unsupported value type for dict: {type(val)}")
    
    def __setitem__(self, k, v):
        if k not in self.val:
            raise ValueError(f"Key {k} not found in dict: {self.shape}")
        self.val[k].set(v)