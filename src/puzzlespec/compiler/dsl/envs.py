from dataclasses import dataclass
from . import ast, ir, ir_types as irT
import typing as tp

class TypeEnv:
    def __init__(self, vars: tp.Dict[int, irT.Type_] = None):
        self.vars = vars if vars is not None else {}

    def __getitem__(self, sid: int) -> irT.Type_:
        return self.vars.get(sid, None)

    def __contains__(self, sid: int):
        return sid in self.vars

    def copy(self, sids: tp.Set[int] = None) -> 'TypeEnv':
        if sids is None:
            sids = self.vars.keys()
        return TypeEnv(vars={sid: self.vars[sid] for sid in sids})

    def add(self, sid: int|str, sort: irT.Type_):
        if sid in self.vars:
            raise ValueError(f"Variable with sid={sid} already defined")
        self.vars[sid] = sort



# Symbol table that stores params/vars and their role. 
# There is an annoying circular dependency with params, so these have sid as their name
@dataclass
class SymEntry:
    name: str
    role: str
    src: str = ""

class SymTable:
    def __init__(self, entries: tp.Dict[int, SymEntry] =None, name_to_sid: tp.Dict[str, int] = None, sid: int = 0):
        self.entries = entries if entries is not None else {}
        self._name_to_sid = name_to_sid if name_to_sid is not None else {}
        self._sid = sid

    def copy(self, sids: tp.Set[int] = None) -> 'SymTable':
        if sids is None:
            sids = self.entries.keys()
        return SymTable(
            entries={sid: self.entries[sid] for sid in sids},
            name_to_sid={name: sid for name, sid in self._name_to_sid.items() if sid in sids},
            sid=self._sid
        )

    def new_var(self, name: str, role: str):
        assert role in ('P', 'G', 'D')
        if name in self._name_to_sid:
            raise ValueError(f"Var, {name}, already exists")
        entry = SymEntry(name, role)
        sid = self._sid
        self._sid += 1
        self.entries[sid] = entry
        self._name_to_sid[name] = sid
        return sid

    def add_var(self, sid: int, name: str, role: str):
        if sid in self.entries:
            raise ValueError(f"Cannot add var {name} to sid {sid} because it already exists")
        entry = SymEntry(name, role)
        self.entries[sid] = entry
        self._name_to_sid[name] = sid
  
    def __contains__(self, sid):
        return sid in self.entries

    def __getitem__(self, sid):
        return self.entries.get(sid)

    def get_name(self, sid: int) -> str:
        if sid not in self.entries:
            raise ValueError(f"Variable {sid} not found")
        return self.entries[sid].name

    def get_sid(self, name: str) -> int:
        return self._name_to_sid.get(name, None)

    def get_role(self, sid: int):
        if sid not in self.entries:
            raise ValueError(f"Variable {sid} not found")
        return self.entries[sid].role

    def get_params(self) -> tp.List[int]:
        return [sid for sid, e in self.entries.items() if e.role == 'P']

    def get_gen_vars(self) -> tp.List[int]:
        return [sid for sid, e in self.entries.items() if e.role == 'G']

    def get_decision_vars(self) -> tp.List[int|str]:
        return [sid for sid, e in self.entries.items() if e.role == 'D']

    def __iter__(self):
        for sid in self.entries:
            yield sid


#TODO START HERE TOMORROW. unify env by including a unit type for base types
class ShapeEnv:
    # Stores shape information about variables
    # if variable is a base type, stores the unit type
    # if variable is a list, stores the size
    # if variable is a dict, stores the keys
    def __init__(self, shapes: tp.Dict[int, ir.Node] = None):
        if shapes is None:
            shapes: tp.Dict[int, ir.Node] = {}
        self.shapes = {}
        for sid, shape in shapes.items():
            self.add(sid, shape)
    
    def terms_node(self) -> ir.Node:
        return ir.Tuple(*self.shapes.values())

    #def terms(self) -> ast.TupleExpr:
    #    return ast.TupleExpr.make(*[ast.IntExpr.make(size) for size in self.lists.values()], *[ast.ListExpr.make(keys) for keys in self.dicts.values()])

    def make_from_terms_node(self, node: ir.Node):
        terms = node._children
        if len(terms) != len(self.shapes):
            raise ValueError(f"Expected {len(self.shapes)} terms, got {len(terms)}")
        new_shapes = {}
        for sid, shape in zip(self.shapes.keys(), terms):
            new_shapes[sid] = shape
        return ShapeEnv(shapes=new_shapes)

    def add(self, sid: int, shape: ir.Node):
        self.shapes[sid] = shape
   
    def get_shape(self, sid: int) -> tp.Optional[ir.Node]:
        return self.shapes.get(sid, None)

    def __getitem__(self, sid: int):
        return self.get_shape(sid)

