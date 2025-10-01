from ..pass_base import Transform, Context, AnalysisObject, handles
from ...dsl import ir, ast
import typing as tp

class ParamValues(AnalysisObject):
    def __init__(self, **kwargs):
        self.mapping = kwargs

class ParamSubPass(Transform):
    requires = (ParamValues,)
    produces = ()
    name = "param_sub"
    def __init__(self):
        super().__init__()

    def run(self, root: ir.Node, ctx: Context):
        self.param_map = ctx.get(ParamValues).mapping
        return self.visit(root)

    @handles(ir.Param)
    def _(self, node: ir.Param):
        new_val = self.param_map.get(node.name)
        if new_val is not None:
            intExpr = ast.IntExpr.make(new_val)
            return intExpr.node
        return node
