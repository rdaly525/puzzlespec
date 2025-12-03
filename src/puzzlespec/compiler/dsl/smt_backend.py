from .spec import PuzzleSpec
from ..passes.pass_base import Pass, Context, PassManager
from ..passes.transforms.scalarize import Scalarize
from ..passes.transforms.encode_enums import EncodeEnums
# Strategy
# Phase 1: Prep spec to be encodable using SMT
#   - Concretize Domains. All domains must be finite and fixed
#       - Eg Fin(v) -> Fin(fixed_max)
#       - forall(x in Fin(v) f(x)) -> forall(x in Fin(fixed_max), (x<v) => f(x)))
class SMTBackend:
    def __init__(self, spec: PuzzleSpec):
        self.spec = spec

    def generate(self) -> str:
        spec = self.spec
        # PromoteDomainsToUniverse (TODO)
        # ExpandFiniteUniverses (TODO)
        # EncodeEnums
        print("Before EncodeEnums:")
        spec = spec.transform(EncodeEnums(), ctx=Context(spec.envs_obj))
        spec.pretty_print()
        #spec = spec.optimize()
        #spec.pretty_print()
        assert 0

       
        print(self.spec.pretty())
        # ScalarizeVars
        print("Before ScalarizeVars:")
        spec = self.spec.transform(Scalarize(), ctx=Context(self.spec.envs_obj))
        spec = spec.optimize(aggressive=True)
        spec.pretty()

        # IntToBV
        #   - Interval analysis for Ints
        #   - Bitvector encoding for Ints
        # Emit using hwtypes