from ..dsl import ir
from .pass_base import PassManager, Context
from .analyses.kind_check import KindCheckingPass, TypeMap
from .transforms import CanonicalizePass, DomainSimplificationPass, BetaReductionPass
from .transforms.refine import RefineSimplify
from .transforms import ConstFoldPass, AlgebraicSimplificationPass
from .transforms.resolve_vars import ResolveBoundVars

def simplify(node: ir.Node) -> ir.Node:
    opt_passes = [
        KindCheckingPass(),
        #ResolveBoundVars(),
        [
            CanonicalizePass(),
            AlgebraicSimplificationPass(),
            ConstFoldPass(),
            DomainSimplificationPass(),
            RefineSimplify(),
            BetaReductionPass(),
        ]
    ]
    ctx = Context()
    pm = PassManager(*opt_passes)
    return pm.run(node, ctx)
