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

    def copy(self) -> 'TypeEnv':
        return TypeEnv(vars=self.vars.copy())

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

    def copy(self) -> 'SymTable':
        return SymTable(entries=self.entries.copy(), name_to_sid=self._name_to_sid.copy(), sid=self._sid)

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


class ShapeEnv:
    # Stores shape information about variables
    # if variable is a base type, no info needed
    # if variable is a list, stores the size
    # if variable is a dict, stores the keys
    def __init__(self, elems: tp.Set[int] = None, lists: tp.Dict[int, ir.Node] = None, dicts: tp.Dict[int, ir.Node] = None):
        self.elems = elems if elems is not None else set()
        self.lists = lists if lists is not None else {}
        self.dicts = dicts if dicts is not None else {}

    def terms_node(self) -> ir.Node:
        return ir.Tuple(ir.Tuple(*self.lists.values()), ir.Tuple(*self.dicts.values()))

    def terms(self) -> ast.TupleExpr:
        return ast.TupleExpr.make(*[ast.IntExpr.make(size) for size in self.lists.values()], *[ast.ListExpr.make(keys) for keys in self.dicts.values()])

    def make_from_terms_node(self, node: ir.Node):
        terms = node._children
        lists_nodes = terms[0]._children
        dicts_nodes = terms[1]._children
        if len(lists_nodes) != len(self.lists):
            raise ValueError(f"Number of lists in terms node does not match number of lists in shape env")
        if len(dicts_nodes) != len(self.dicts):
            raise ValueError(f"Number of dicts in terms node does not match number of dicts in shape env")
        new_lists = {sid: lists_nodes[i] for i, (sid, _) in enumerate(self.lists.items())}
        new_dicts = {sid: dicts_nodes[i] for i, (sid, _) in enumerate(self.dicts.items())}
        return ShapeEnv(elems=self.elems, lists=new_lists, dicts=new_dicts)

    def add(self, sid: int, T: irT.Type_, shape: ir.Node=None):
        if sid in self.elems or sid in self.lists or sid in self.dicts:
            raise ValueError(f"Cannot add shape {T} to sid {sid} because it already exists")
        match T:
            case irT.ListT():
                self.lists[sid] = shape
            case irT.DictT():
                self.dicts[sid] = shape
            case irT.Bool | irT.Int | irT.CellIdxT:
                assert shape is None
                self.elems.add(sid)
            case _:
                raise NotImplementedError(f"Shape type {T} not supported")
   
    def get_shape(self, sid: int) -> tp.Optional[ir.Node]:
        if sid in self.elems:
            return None
        elif sid in self.lists:
            return self.lists[sid]
        elif sid in self.dicts:
            return self.dicts[sid]
        else:
            raise ValueError(f"Shape not found for sid {sid}")

