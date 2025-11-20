from ..pass_base import Transform, Context, AnalysisObject, handles
from ...dsl import ir, ast
import typing as tp

class ResolveBoundVars(Transform):
    #_debug=True
    enable_memoization = False
    requires = ()
    produces = ()
    name = "resolve_bound_vars"
    
    def run(self, root: ir.Node, ctx: Context):
        self.bctx = {}
        return self.visit(root)

    @handles(ir._BoundVarPlaceholder)
    def _(self, bv: ir._BoundVarPlaceholder):
        #new_T, = self.visit(bv)
        bv_def_level = self.bctx[bv]
        bv_use_level = len(self.bctx) - 1
        db_idx = bv_use_level - bv_def_level
        assert db_idx >= 0
        return ir.BoundVar(idx=db_idx)
    
    # pushes/pops binding contexts
    @handles(ir._LambdaPlaceholder)
    def _(self, node: ir._LambdaPlaceholder):
        T, bv, body = node._children
        self.bctx[bv] = len(self.bctx)
        new_body = self.visit(body)
        new_T = self.visit(T)
        self.bctx.popitem()
        return ir.Lambda(new_T, new_body)

class VarMap(AnalysisObject):
    def __init__(self, sid_to_T):
        self.sid_to_T = sid_to_T

# This will replace _VarPlaceHolder
class ResolveFreeVars(Transform):
    #_debug=True
    requires = ()
    produces = (VarMap,)
    name = "resolve_free_vars"
    
    def run(self, root: ir.Node, ctx: Context):
        self.sid_to_T = {}
        new_root = self.visit(root)
        ctx.add(VarMap(self.sid_to_T))
        return new_root

    @handles(ir._VarPlaceholder)
    def _(self, v: ir._VarPlaceholder):
        new_T, = self.visit_children(v)
        self.sid_to_T[v.sid] = new_T
        return ir.VarRef(v.sid)