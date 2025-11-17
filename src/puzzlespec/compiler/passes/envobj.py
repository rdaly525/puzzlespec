from .pass_base import AnalysisObject
from ..dsl.envs import SymTable, TypeEnv

# Common Analysis Object
class EnvsObj(AnalysisObject):
    def __init__(self, sym: SymTable, tenv: TypeEnv):
        self.sym = sym
        self.tenv = tenv 
