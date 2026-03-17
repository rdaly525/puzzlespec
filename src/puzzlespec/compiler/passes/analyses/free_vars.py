from ..pass_base import Analysis, Context, AnalysisObject, handles
from ..envobj import EnvsObj, SymTable
from ...dsl import ir, ast
import typing as tp

def get_free_vars(node: ir.Node):
    vars = FreeVarsPass()(node, Context())
    return vars.vars

class FreeVars(AnalysisObject):
    def __init__(self, vars):
        assert isinstance(vars, set)
        self.vars = vars

# Checks BVHOAS
class FreeVarsPass(Analysis):
    #_debug=True
    requires = ()
    produces = ()
    name = "freevars"
    enable_memoization=False

    def run(self, root, ctx):
        self.vmap = {}
        self.nmap = {}
        vars = self.visit(root)
        return FreeVars(vars)

    def add_fvars(self, node, fvars):
        if not (isinstance(node, ir.Type) and node.ref is not None):
            return
        if node in self.vmap:
            if self.vmap[node] != fvars:
                raise ValueError()
        else:
            #print(node.__class__.__name__, str(node._hash)[:5], node, fvars)
            self.vmap[node] = set(fvars)
            self.nmap[node] = node

    def visit(self, node: ir.Node):
        # Visit all Node-valued parts (children + T + obl + ref + view)
        fvars = set()
        for c in node.all_nodes:
            fvars |= self.visit(c)
        self.add_fvars(node, fvars)
        return fvars

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        fvars = set()
        for c in node.all_nodes:
            fvars |= self.visit(c)
        fvars -= {node.bv_name}
        self.add_fvars(node, fvars)
        return fvars

    @handles(ir.PiTHOAS)
    def _(self, node: ir.PiTHOAS):
        fvars = set()
        for c in node.all_nodes:
            fvars |= self.visit(c)
        fvars -= {node.bv_name}
        self.add_fvars(node, fvars)
        return fvars

    @handles(ir.BoundVarHOAS)
    def _(self, bv: ir.BoundVarHOAS):
        fvars = {bv.name}
        for c in bv.all_nodes:
            fvars |= self.visit(c)
        self.add_fvars(bv, fvars)
        return fvars
