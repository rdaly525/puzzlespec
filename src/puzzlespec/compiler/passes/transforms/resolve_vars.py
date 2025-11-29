from ..pass_base import Transform, Context, AnalysisObject, handles
from ...dsl import ir, ast
import typing as tp

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
        self._check_no_placeholders(new_root)
        return new_root

    def _check_no_placeholders(self, node):
        if isinstance(node, (ir.BoundVarHOAS, ir.LambdaHOAS, ir.PiTHOAS)):
            raise ValueError(f"Failed resolve bound, found {node}")
        for c in node._children:
            self._check_no_placeholders(c)

    @handles(ir.LambdaHOAS)
    def _(self, node):
        T, bv, body = node._children
        new_T = self.visit(T)
        self.stack.append(bv)
        new_body = self.visit(body)
        self.stack.pop()
        return ir.Lambda(new_T, new_body)

    @handles(ir.PiTHOAS)
    def _(self, node):
        bv, bodyT = node._children
        bv_T = self.visit(bv.T)
        self.stack.append(bv)
        new_bodyT = self.visit(bodyT)
        self.stack.pop()
        return ir.PiT(bv_T, new_bodyT)

    @handles(ir.BoundVarHOAS)
    def _(self, use):
        # find binder in stack from the end
        for depth_from_end, binder in enumerate(reversed(self.stack)):
            if binder is use:
                return ir.BoundVar(idx=depth_from_end)
        # if we get here, no binder in scope
        raise ValueError(f"Unbound placeholder {use} (stack={self.stack})")

#class ResolveBoundVars(Transform):
#    _debug=True
#    enable_memoization = False
#    requires = ()
#    produces = ()
#    name = "resolve_bound_vars"
#    cse=True
#    
#    def run(self, root: ir.Node, ctx: Context):
#        self.bctx = {}
#        new_root = self.visit(root)
#        def check(node: ir.Node):
#            if isinstance(node, (ir.BoundVarHOAS, ir.LambdaHOAS, ir.PiTHOAS)):
#                raise ValueError(f"Failed resolve bound, found {node}")
#            for c in node._children:
#                check(c)
#        return new_root
#
#    def print_ctx(self):
#        print("CONTEXT")
#        for bv, i in self.bctx.items():
#            print("  BV", str(id(bv))[-5:], i)
#        print()
#
#    @handles(ir.BoundVarHOAS)
#    def _(self, bv: ir.BoundVarHOAS):
#        new_T, = self.visit_children(bv)
#        print("BV ", str(id(bv))[-5:], new_T)
#        self.print_ctx()
#        bv_def_level = self.bctx[bv]
#        bv_use_level = len(self.bctx) - 1
#        db_idx = bv_use_level - bv_def_level
#        assert db_idx >= 0
#        return ir.BoundVar(idx=db_idx)
#    
#    # pushes/pops binding contexts
#    @handles(ir.LambdaHOAS)
#    def _(self, node: ir.LambdaHOAS):
#        T, bv, body = node._children
#        new_T = self.visit(T)
#        self.bctx[bv] = len(self.bctx)
#        print("LAM", str(id(node))[-5:])
#        self.print_ctx()
#        new_body = self.visit(body)
#        del self.bctx[bv]
#        return ir.Lambda(new_T, new_body)
#    
#    @handles(ir.PiTHOAS)
#    def _(self, node: ir.PiTHOAS):
#        bv, bodyT = node._children
#        bv_T = self.visit(bv.T)
#        self.bctx[bv] = len(self.bctx)
#        print("PIT", str(id(node))[-5:])
#        self.print_ctx()
#        new_bodyT = self.visit(bodyT)
#        del self.bctx[bv]
#        return ir.PiT(bv_T, new_bodyT)


class VarMap(AnalysisObject):
    def __init__(self, sid_to_T):
        self.sid_to_T = sid_to_T

# This will replace _VarPlaceHolder
class ResolveFreeVars(Transform):
    requires = ()
    produces = (VarMap,)
    name = "resolve_free_vars"
    #_debug=True
    
    def run(self, root: ir.Node, ctx: Context):
        self.sid_to_T = {}
        new_root = self.visit(root)
        return new_root, VarMap(self.sid_to_T)

    @handles(ir.VarHOAS)
    def _(self, v: ir.VarHOAS):
        new_T, = self.visit_children(v)
        self.sid_to_T[v.sid] = new_T
        return ir.VarRef(v.sid)