from __future__ import annotations
from . import ir, ast
from .spec import PuzzleSpec
from ..passes.transforms.substitution import SubMapping, SubstitutionPass
from ..passes.pass_base import Context
import typing as tp
import numpy as np
from abc import abstractmethod
import itertools as it

def _make_var(T: ir.Type, path: tp.Tuple):
    if isinstance(T, (ir.BoolT, ir.IntT)):
        return SetterBase(T, path)
    if isinstance(T, ir.PiT):
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

def iterate(dom: ir.Value):
    for d in _iterate(dom):
        if isinstance(d, tuple):
            yield d
        else:
            yield (d,)

def _iterate(dom: ir.Value):
    if isinstance(dom, ir.Fin):
        n = dom._children[1]
        if not isinstance(n, ir.Lit):
            raise ValueError(f"{n} is not constant")
        yield from range(n.val)
    elif isinstance(dom, ir.Range):
        lo, hi = dom._children[1:]
        if not isinstance(lo, ir.Lit) or not isinstance(hi, ir.Lit):
            raise ValueError(f"{lo} or {hi} is not constant")
        yield from range(lo.val, hi.val)
    elif isinstance(dom, ir.CartProd):
        doms = dom._children[1:]
        yield from it.product(*[_iterate(dom) for dom in doms])
    else:
        raise NotImplementedError(f"Unsupported domain type: {type(dom)}")


class SetterFunc(_Setter):
    def __post_init__(self):
        # Check if it depends on any variable
        assert isinstance(self.T, ast.PiType)
        self.val = None
        ...

    @property
    def _is_set(self):
        return self.val is not None
        return all(val._is_set for val in self._val.values())

    def _get_val(self):
        return self.val

    def set(self, val):
        if not isinstance(val, ast.FuncExpr):
            raise NotImplementedError()
        self.val = val

    def set_lam(self, fn: tp.Callable):
        terms = []
        assert isinstance(self.T, ast.PiType)
        for dom_idx in iterate(self.T.domain.node):
            val = fn(*dom_idx)

            e = ast.Expr.make(val)
            terms.append(e.node)
        layout = ir._DenseLayout(num_elems=len(terms))
        self.set(ast.wrap(ir.FuncLit(self.T.node, self.T.domain.node, *terms, layout=layout)))
    
    def __setitem__(self, k, v):
        if k not in self._val:
            raise ValueError(f"Key {k} not found in dict: {self.shape}")
        self._val[k].set(v)
    
    def _constraints(self, var: 'ast.Expr'):
        from . import ast
        for k, v in self._val.items():
            yield from v._constraints(var[ast.Expr.make(k)])