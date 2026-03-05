from ..dsl import ir
from .pass_base import PassManager, Context
from .analyses.type_check import TypeCheckingPass, TypeMap
from .transforms import CanonicalizePass, DomainSimplificationPass
from .transforms.beta_reduction import BetaReductionHOAS, BetaReductionPass
#from .transforms.refine import RefineSimplify
from .transforms import ConstFoldPass, AlgebraicSimplificationPass
from .transforms.resolve_vars import ResolveBoundVars
from .transforms.ord import OrdSimplificationPass
from .transforms.guard_opt import GuardLift, GuardOpt
import enum

def simplify(node: ir.Node, hoas: bool=False, verbose: int = 0, max_iter: int=5) -> ir.Node:
    opt_passes = [
        TypeCheckingPass(),
        GuardLift(),
        [
            CanonicalizePass(),
            ConstFoldPass(),
            AlgebraicSimplificationPass(),
            DomainSimplificationPass(),
            GuardOpt(),
            #RefineSimplify(),
            BetaReductionHOAS() if hoas else BetaReductionPass()
        ],
    ]
    ctx = Context()
    #pm = PassManager(*opt_passes, OrdSimplificationPass(), *opt_passes, verbose=verbose, max_iter=max_iter)
    pm = PassManager(*opt_passes, verbose=verbose)
    return pm.run(node, ctx)
