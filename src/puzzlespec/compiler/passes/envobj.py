from .pass_base import AnalysisObject
from ..dsl.envs import SymTable, TypeEnv
import typing as tp
from ..dsl import ir

# Common Analysis Object
class EnvsObj(AnalysisObject):
    persistent = True
    def __init__(self, sym: SymTable, tenv: TypeEnv):
        self.sym = sym
        self.tenv = tenv 

class OblsObj(AnalysisObject):
    def __init__(self, obls: tp.Mapping[int, ir.Node]):
        self.obls = obls