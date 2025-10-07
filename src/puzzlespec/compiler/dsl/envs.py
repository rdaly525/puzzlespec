from dataclasses import dataclass
from . import ast, ir, ir_types as irT
import typing as tp

class TypeEnv:
    def __init__(self):
        self.vars = {} # sid -> T

    def __getitem__(self, sid: int|str) -> irT.Type_:
        return self.vars.get(sid, None)

    def __contains__(self, sid: int|str):
        return sid in self.vars
    
    def add(self, sid: int|str, sort: irT.Type_):
        if sid in self.vars:
            raise ValueError(f"Variable with cid={cid} already defined")
        self.vars[sid] = sort

# Symbol table that stores params/vars and their role. 
# There is an annoying circular dependency with params, so these have sid as their name
@dataclass
class SymEntry:
    name: str
    role: str
    src: str = ""

class SymTable:
       
    def __init__(self):
        self.entries: tp.Dict[int, SymEntry] = {}
        self._name_to_sid = {}
        self._sid = 0

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
  
    def __contains__(self, sid):
        return sid in self.entries

    def __getitem__(self, sid):
        return self.entries.get(sid)

    def get_name(self, sid: int):
        if sid not in self.entries:
            raise ValueError(f"Variable {sid} not found")
        return self.entries[sid].name

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


class ShapeEnv:
    def __init__(self):
        self.elems = set()
        self.lists = {} # cid -> size
        self.dicts = {} # cid -> keys

    def add_elem(self, cid:int):
        assert cid not in self.elems
        self.elems.add(cid)

    def add_list(self, cid: int, size: ast.IntExpr):
        assert cid not in self.lists
        self.lists[cid] = size

    def add_dict(self, cid: int, keys: ast.ListExpr):
        assert cid not in self.dicts
        self.dicts[cid] = keys

