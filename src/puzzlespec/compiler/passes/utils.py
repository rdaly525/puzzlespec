from ..dsl import ir
from .pass_base import PassManager, Context
from .analyses.type_check import TypeCheckingPass, TypeMap
from .transforms import CanonicalizePass, DomainSimplificationPass
from .transforms.beta_reduction import BetaReductionHOAS, BetaReductionPass
from .transforms.refine import RefineSimplify
from .transforms import ConstFoldPass, AlgebraicSimplificationPass
from .transforms.resolve_vars import ResolveBoundVars

def simplify(node: ir.Node, hoas: bool=False, verbose: int = 2) -> ir.Node:
    opt_passes = [
        TypeCheckingPass(),
        [
            CanonicalizePass(),
            ConstFoldPass(),
            AlgebraicSimplificationPass(),
            DomainSimplificationPass(),
            #RefineSimplify(),
            BetaReductionHOAS() if hoas else BetaReductionPass()
        ]
    ]
    ctx = Context()
    pm = PassManager(*opt_passes, verbose=verbose)
    return pm.run(node, ctx)
