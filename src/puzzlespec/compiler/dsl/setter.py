from multiprocessing import Value
from . import ir, ir_types as irT
from .spec import PuzzleSpec
import typing as tp
import numpy as np
from abc import abstractmethod

def _make_clue_var(shape: ir.Node, T: irT.Type_, path: tp.Tuple):
    match (T):
        case irT.Int | irT.Bool:
            return SetterVarBase(T, shape, path)
        case irT.DictT(keyT, valT):
            if not keyT in (irT.TupleT(irT.Int, irT.Int), irT.Int):
                raise NotImplementedError(f"Unsupported key type for dict: {keyT}")
            return SetterVarDict(T, shape, path)

class Setter:
    def __init__(self, spec: PuzzleSpec, role='G'):
        self.__dict__['_spec'] = spec
        self.__dict__['_vars'] = {}
        self.__dict__['_role'] = role
        for sid in spec.sym:
            if spec.sym.get_role(sid)==self._role:
                name = spec.sym.get_name(sid)
                T = spec.tenv[sid]
                shape = spec.evaluate(spec.shape_env[sid])
                self.__dict__['_vars'][name] = _make_clue_var(shape, T, (sid,))

    def __getattr__(self, name: str) -> tp.Any:
        if name in self.__dict__['_vars']:
            return self.__dict__['_vars'][name]
        else:
            raise AttributeError(f"Attribute {name} not found")

    def __setattr__(self, k, v):
        if k in self.__dict__['_vars']:
            return self.__dict__['_vars'][k].set(v)
        else:
            raise ValueError(f"{k} is not a variable with role {self.role}")

    def build(self) -> PuzzleSpec:
        from . import ast
        spec = self.__dict__['_spec']
        vars = self.__dict__['_vars']
        # Add as constraints
        new_constraints = []
        for name, var in vars.items():
            sid = spec.sym.get_sid(name)
            ast_var = ast.wrap(ir.VarRef(sid), var.T)
            new_constraints += [e.node for e in var._constraints(ast_var)]
        
        new_rules = ir.List(*spec._rules._children, *new_constraints)
        ps = PuzzleSpec(
            name=spec.name,
            desc=spec.desc,
            topo=spec.topo,
            sym=spec.sym,
            tenv=spec.tenv,
            shape_env=spec.shape_env,
            rules=new_rules
        )
        return ps.optimize()

class SetterVar:
    def __init__(self, T: irT.Type_, shape: ir.Node, path: tp.Tuple[tp.Any]):
        self.T = T
        self.shape = shape
        self.path = path
        self.__post_init__()

    @abstractmethod
    def _is_set(self):
        ...
    
    @abstractmethod
    def set(self, val):
        ...

    @abstractmethod
    def _constraints(self, val: 'ast.Expr'):
        ...


class SetterVarBase(SetterVar):
    def __post_init__(self):
        self.val = None

    @property
    def _is_set(self):
        return self.val is not None

    def set(self, val):
        self.val = self.T.cast_as(val)

    def __setitem__(self, key, val):
        if key==():
            self.set(val)
        else:
            raise ValueError(f"Wrong key type for {self.path}: {self.__class__}")

    def _constraints(self, var: 'ast.Expr'):
        if self.val is not None:
            yield var==self.val

class SetterVarDict(SetterVar):
    def __post_init__(self):
        if not self.T.keyT in (irT.TupleT(irT.Int, irT.Int), irT.Int):
            raise NotImplementedError(f"Unsupported key type for dict: {self.T.keyT}")
        # check if shape is a concrete List of concrete elements:
        self.__dict__['_val'] = {k: SetterVarBase(self.T.valT, ir.Unit, self.path + (k,)) for k in self.shape}

    @property
    def _is_set(self):
        return all(val._is_set for val in self._val.values())

    def set(self, val: tp.Any):
        if isinstance(val, tp.Dict):
            for k, v in val.items():
                self[k] = v
        elif isinstance(val, np.ndarray):
            # TODO verify shape
            for k, v in np.ndenumerate(val):
                self[k] = v
        else:
            raise ValueError(f"Unsupported value type for dict: {type(val)}")
    
    def __setitem__(self, k, v):
        if k not in self._val:
            raise ValueError(f"Key {k} not found in dict: {self.shape}")
        self._val[k].set(v)
    
    def _constraints(self, var: 'ast.Expr'):
        from . import ast
        for k, v in self._val.items():
            yield from v._constraints(var[ast.Expr.make(k)])