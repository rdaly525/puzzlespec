from ..pass_base import Transform, Context, AnalysisObject, handles
from ...dsl import ir, ast
import typing as tp

# Turns placeholder bound vars/lambdas into proper bound vars/lambdas with de bruijn indices
# Used immediately to translate DSL constraints to a standard form
class ResolveBoundVars(Transform):
    enable_memoization = False
    requires = ()
    produces = ()
    name = "resolve_bound_vars"
    
    def run(self, root: ir.Node, ctx: Context):
        self.bctx = {}
        return self.visit(root)

    @handles(ir._BoundVarPlaceholder)
    def _(self, bv: ir._BoundVarPlaceholder):
        bv_def_level = self.bctx[bv]
        bv_use_level = len(self.bctx) - 1
        db_idx = bv_use_level - bv_def_level
        assert db_idx >= 0
        return ir.BoundVar(db_idx)
    
    # pushes/pops binding contexts
    @handles(ir._LambdaPlaceholder)
    def _(self, node: ir._LambdaPlaceholder):
        bv, body = node._children
        self.bctx[bv] = len(self.bctx)
        new_body = self.visit(body)
        self.bctx.popitem()
        return ir.Lambda(new_body, node.paramT)
