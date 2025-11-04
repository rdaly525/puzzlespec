# Import all the analysis passes and their corresponding Analysis Object (if exists)
from .type_inference import TypeInferencePass, TypeValues, TypeEnv_
from .pretty_printer import PrettyPrinterPass, PrettyPrintedExpr
from .constraint_categorizer import ConstraintCategorizer, ConstraintCategorizerVals
from .ssa_printer import SSAPrinter, SSAResult
from ..pass_base import AnalysisObject
from ...dsl.envs import SymTable, TypeEnv, DomEnv

# Common Analysis Object
class EnvsObj(AnalysisObject):
    def __init__(self, sym: SymTable, tenv: TypeEnv, domenv: DomEnv):
        self.sym = sym
        self.tenv = tenv
        self.domenv = domenv
