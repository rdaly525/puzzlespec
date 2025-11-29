from __future__ import annotations
from . import ir, ast, utils
from .spec import PuzzleSpec
from ..passes.transforms.substitution import SubMapping, SubstitutionPass
from ..passes.pass_base import Context
import typing as tp
import numpy as np
from abc import abstractmethod

def _make_var(T: ir.Type, path: tp.Tuple):
    if isinstance(T, (ir.BoolT, ir.IntT)):
        return SetterBase(T, path)
    if isinstance(T, ir.FuncT):
        return SetterFunc(T, path)
    raise NotImplementedError(f"{type(T)}")

class VarSetter:
    def __init__(self, spec: PuzzleSpec):
        self.__dict__['_spec'] = spec
        self.__dict__['_vars'] = {}
        for sid in spec.sym:
            name = spec.sym.get_name(sid)
            T = spec.tenv[sid]
            self.__dict__['_vars'][name] = _make_var(T, (sid,))

    def __getattr__(self, name: str) -> _Setter:
        if name in self.__dict__['_vars']:
            return self.__dict__['_vars'][name]
        else:
            raise AttributeError(f"Attribute {name} not found")

    def __setattr__(self, k, v):
        if k in self.__dict__['_vars']:
            return self.__dict__['_vars'][k].set(v)
        else:
            raise ValueError(f"{k} is not a variable")

    def build(self) -> PuzzleSpec:
        spec: PuzzleSpec = self.__dict__['_spec']
        vars: tp.Mapping[str, _Setter] = self.__dict__['_vars']
        # Add as constraints
        subs: tp.List[tp.Tuple[int, ast.Expr]] = []
        for name, varSet in vars.items():
            if not varSet._is_set:
                continue
            sid = spec.sym.get_sid(name)
            subs.append((sid, varSet._get_val()))
        
        submap = SubMapping()
        for sid, e in subs:
            submap.add(
                match = lambda node, sid=sid: isinstance(node, ir.VarRef) and node.sid==sid,
                replace = lambda node, val=e.node: val
            )
        if len(subs) > 0:
            ctx = Context(submap)
            sub_spec = spec.transform(SubstitutionPass(), ctx=ctx, verbose=True)
            opt = sub_spec.optimize()
            return opt
        print("NOTHING SET")
        return spec

class _Setter:
    def __init__(self, T: ir.Type, path: tp.Tuple[tp.Any]):
        self.T = ast.wrapT(T)
        self.path = path
        self.__post_init__()

    @abstractmethod
    def _is_set(self):
        ...
    
    @abstractmethod
    def _get_val(self) -> ast.Expr:
        ...
    
    @abstractmethod
    def _constraints(self, val: 'ast.Expr'):
        ...


class SetterBase(_Setter):
    def __post_init__(self):
        self.val = None

    @property
    def _is_set(self):
        return self.val is not None

    def set(self, val):
        val = ast.Expr.make(val)
        if not type(self.T) is type(val.T):
            raise ValueError(f"Cannot set {self.path} with T={self.T} to be {val}")
        self.val = val
    
    def _get_val(self):
        return self.val

    def _constraints(self, var: 'ast.Expr'):
        if self.val is not None:
            yield var==self.val


class SetterFunc(_Setter):
    def __post_init__(self):
        # Check if it depends on any variable
        assert isinstance(self.T, ast.FuncType)
        self.concrete = utils._is_concrete(self.T.domain.node)
        self.val = None
        ...

    @property
    def _is_set(self):
        return self.val is not None

    def _get_val(self):
        return self.val

    def set(self, val):
        if not self.concrete:
            raise ValueError("Cannot only set concrete vars")
        if not isinstance(val, ast.FuncExpr):
            raise NotImplementedError()
        self.val = val

    def set_lam(self, fn: tp.Callable):
        terms = []
        assert isinstance(self.T, ast.FuncType)

        val_map = {}
        for i, elem in enumerate(utils._iterate(self.T.domain.node)):
            val = fn(utils._unpack(elem))
            e = ast.Expr.make(val)
            terms.append(e.node)
            val_map[elem._key] = i
        layout = ir._DenseLayout(val_map=val_map)
        self.set(ast.wrap(ir.FuncLit(self.T.node, self.T.domain.node, *terms, layout=layout)))
    
    def __setitem__(self, k, v):
        if k not in self._val:
            raise ValueError(f"Key {k} not found in dict: {self.shape}")
        self._val[k].set(v)
    
    def _constraints(self, var: 'ast.Expr'):
        from . import ast
        for k, v in self._val.items():
            yield from v._constraints(var[ast.Expr.make(k)])