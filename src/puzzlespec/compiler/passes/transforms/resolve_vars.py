from ..pass_base import Transform, Context, AnalysisObject, handles
from ..envobj import EnvsObj, SymTable
from ...dsl import ir, ast
import typing as tp

def resolve_bound_vars(root: ir.Node) -> ir.Node:
    ctx = Context()
    new_root = ResolveBoundVars().run(root, ctx)
    return new_root

class ResolveBoundVars(Transform):
    #_debug=True
    enable_memoization = False
    requires = ()
    produces = ()
    name = "resolve_bound_vars"
    cse=True

    def run(self, root, ctx):
        self.stack = []
        new_root = self.visit(root)
        self._check_no_hoas(new_root)
        return new_root

    def _check_no_hoas(self, node):
        if isinstance(node, (ir.BoundVarHOAS, ir.LambdaHOAS, ir.LambdaTHOAS)):
            raise ValueError(f"Failed resolve bound, found {node}")
        for c in node._children:
            self._check_no_hoas(c)

    @handles(ir.LambdaHOAS)
    def _(self, node):
        T, bv, body = node._children
        new_T = self.visit(T)
        self.stack.append(bv)
        new_body = self.visit(body)
        self.stack.pop()
        return ir.Lambda(new_T, new_body)

    @handles(ir.Lambda)
    def _(self, node):
        T, body = node._children
        new_T = self.visit(T)
        self.stack.append(None)
        new_body = self.visit(body)
        self.stack.pop()
        return ir.Lambda(new_T, new_body)

    @handles(ir.LambdaTHOAS)
    def _(self, node):
        bv, bodyT = node._children
        bv_T = self.visit(bv.T)
        self.stack.append(bv)
        new_bodyT = self.visit(bodyT)
        self.stack.pop()
        return ir.LambdaT(bv_T, new_bodyT)

    @handles(ir.LambdaT)
    def _(self, node):
        argT, bodyT = node._children
        new_argT = self.visit(argT)
        self.stack.append(None)
        new_bodyT = self.visit(bodyT)
        self.stack.pop()
        return ir.LambdaT(new_argT, new_bodyT)

    @handles(ir.BoundVarHOAS)
    def _(self, use):
        # find binder in stack from the end
        for depth_from_end, binder in enumerate(reversed(self.stack)):
            if binder is use:
                return ir.BoundVar(idx=depth_from_end)
        # if we get here, no binder in scope
        raise ValueError(f"Unbound placeholder {use} (stack={self.stack})")


class VarMap(AnalysisObject):
    def __init__(self, sid_to_T):
        self.sid_to_T = sid_to_T

# This will replace _VarPlaceHolder
class ResolveFreeVars(Transform):
    requires = (EnvsObj,)
    produces = (EnvsObj,)
    name = "resolve_free_vars"
    #_debug=True
    
    def run(self, root: ir.Node, ctx: Context):
        self.sym: SymTable = ctx.get(EnvsObj).sym
        new_root = self.visit(root)
        return new_root, EnvsObj(self.sym)

    @handles(ir.VarHOAS)
    def _(self, v: ir.VarHOAS):
        new_T, = self.visit_children(v)
        sid = self.sym.new_var(v.name, v.metadata)
        return ir.VarRef(new_T, sid, v.name)