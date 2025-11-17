from dataclasses import dataclass
from . import ir
import typing as tp

class TypeEnv:
    def __init__(self, vars: tp.Dict[int, ir.Type] = None):
        self.vars = vars if vars is not None else {}

    def __getitem__(self, sid: int) -> ir.Type:
        return self.vars.get(sid, None)

    def __contains__(self, sid: int):
        return sid in self.vars

    def copy(self, sids: tp.Set[int] = None) -> 'TypeEnv':
        if sids is None:
            sids = self.vars.keys()
        return TypeEnv(vars={sid: self.vars[sid] for sid in sids})

    def add(self, sid: int, T: ir.Type):
        if sid in self.vars:
            raise ValueError(f"Variable with sid={sid} already defined")
        self.vars[sid] = T



# Symbol table that stores params/vars and their role. 
# There is an annoying circular dependency with params, so these have sid as their name
@dataclass
class SymEntry:
    name: str
    role: str
    public: bool
    src: str = ""

class SymTable:
    def __init__(self, entries: tp.Dict[int, SymEntry] =None, sid: int = 0):
        self.entries = entries if entries is not None else {}
        self._name_to_sid = {e.name:sid for sid, e in self.entries.items()}
        self._sid = sid

    def copy(self, sids: tp.Set[int] = None) -> 'SymTable':
        if sids is None:
            sids = self.entries.keys()
        return SymTable(
            entries={sid: self.entries[sid] for sid in sids},
            name_to_sid={name: sid for name, sid in self._name_to_sid.items() if sid in sids},
            sid=self._sid
        )

    def new_var(self, name: str, role: str, public: bool):
        sid = self._sid
        self._sid += 1
        self.add_var(sid, name, role, public)
        return sid

    def add_var(self, sid: int, name: str, role: str, public: bool):
        if name in self._name_to_sid:
            raise ValueError(f"Var, {name}, already exists")
        assert role in ('P', 'G', 'D')
        if sid in self.entries:
            raise ValueError(f"Cannot add var {name} to sid {sid} because it already exists")
        entry = SymEntry(name, role, public)
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

#@dataclass
#class DomEnvEntry:
#    dom_nodes: tp.Tuple[ir.Node]
#    #domTs: tp.Tuple[irT.DomT]

# sid -> (Dom, Dom, ...)
# 1 Dom means 'base' variable with a domain constraint
# 2 Doms means Func[Dom0 -> Dom1]
# 3 Doms means Func[Dom0 -> Func[Dom1 -> Dom2]

#DomsT = tp.Tuple[ir.Node, ...]
#class DomEnv:
#    # Stores Domain Information about variables
#    def __init__(self, entries: tp.Dict[int, DomsT] = None):
#        self.entries = {}
#        if entries is not None:
#            for sid, doms in entries.items():
#                self.add(sid, doms)
#    
#    def add(self, sid: int, doms: DomsT):
#        self.entries[sid] = doms
#   
#    def get_doms(self, sid: int) -> DomsT:
#        return self[sid]
#
#    def __getitem__(self, sid) -> DomsT:
#        e = self.entries.get(sid, None)
#        if e is None:
#            raise ValueError(f"Variable {sid} not found in DomEnv")
#        return e