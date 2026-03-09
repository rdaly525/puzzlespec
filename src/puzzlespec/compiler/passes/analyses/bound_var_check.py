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
        print(root)
        self.bv_stack = set()
        self.visit(root)
        return BVCheck()

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        T, body = node._children
        bv_name = node.bv_name
        if bv_name in self.bv_stack:
            raise ValueError(f"Should not see {bv_name}")
        self.visit(T)
        self.bv_stack.add(bv_name)
        self.visit(body)
        self.bv_stack.remove(bv_name)

    @handles(ir.PiTHOAS)
    def _(self, node: ir.PiTHOAS):
        argT, resT = node._children
        bv_name = node.bv_name
        if bv_name in self.bv_stack:
            raise ValueError(f"Should not see {bv_name}")
        self.visit(argT)
        self.bv_stack.add(bv_name)
        self.visit(resT)
        self.bv_stack.remove(bv_name)

    @handles(ir.BoundVarHOAS)
    def _(self, bv: ir.BoundVarHOAS):
        if bv.name not in self.bv_stack:
            raise ValueError(f"Unbound placeholder {bv} (stack={self.bv_stack})")
        self.visit_children(bv)

