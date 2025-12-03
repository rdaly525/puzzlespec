from .pass_base import AnalysisObject
from ..dsl.envs import SymTable
import typing as tp
from ..dsl import ir

# Common Analysis Object
class EnvsObj(AnalysisObject):
    persistent = True
    def __init__(self, sym: SymTable):
        self.sym = sym

class OblsObj(AnalysisObject):
    def __init__(self, obls: tp.Mapping[int, ir.Node]):
        self.obls = obls