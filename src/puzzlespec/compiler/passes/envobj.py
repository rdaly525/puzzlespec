from .pass_base import AnalysisObject
from ..dsl.envs import SymTable, DomEnv

# Common Analysis Object
class EnvsObj(AnalysisObject):
    def __init__(self, sym: SymTable, domenv: DomEnv, penv):
        self.sym = sym
        self.domenv = domenv
        self.penv = penv
