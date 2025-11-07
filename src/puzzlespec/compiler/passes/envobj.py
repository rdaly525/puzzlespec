from .pass_base import AnalysisObject
from ..dsl.envs import SymTable, TypeEnv, DomEnv

# Common Analysis Object
class EnvsObj(AnalysisObject):
    def __init__(self, sym: SymTable, tenv: TypeEnv, domenv: DomEnv):
        self.sym = sym
        self.tenv = tenv
        self.domenv = domenv
