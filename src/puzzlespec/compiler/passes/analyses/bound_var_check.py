from ..pass_base import Analysis, Context, AnalysisObject, handles
from ..envobj import EnvsObj, SymTable
from ...dsl import ir, ast
import typing as tp


class BVCheck(AnalysisObject): pass

# Checks BVHOAS
class CheckBoundVars(Analysis):
    #_debug=True
    requires = ()
    produces = ()
    name = "check_bound_vars"

    def run(self, root, ctx):
        self.bv_stack = set()
        self.visit(root)
        return BVCheck()

    @handles(ir.LambdaHOAS)
    def _(self, node):
        T, bv, body = node._children
        if bv.name in self.bv_stack:
            raise ValueError(f"Should not see {bv}")
        self.visit(T)
        self.visit(bv.T)
        self.bv_stack.add(bv.name)
        self.visit(body)
        self.bv_stack.remove(bv.name)

    @handles(ir.LambdaTHOAS)
    def _(self, node):
        bv, bodyT = node._children
        if bv.name in self.bv_stack:
            raise ValueError(f"Should not see {bv}")
        self.visit(bv.T)
        self.bv_stack.add(bv.name)
        self.visit(bodyT)
        self.bv_stack.remove(bv.name)

    @handles(ir.BoundVarHOAS)
    def _(self, bv: ir.BoundVarHOAS):
        if bv.name not in self.bv_stack:
            raise ValueError(f"Unbound placeholder {bv} (stack={self.bv_stack})")
        self.visit_children(bv)

