from ..pass_base import Transform, Context, AnalysisObject, handles
from ...dsl import ir, ast
import typing as tp
from dataclasses import dataclass


# All the work is done in the memoization of the pass base
class CSE(Transform):
    requires = ()
    produces = ()
    name = "cse"
    enable_memoization=False
    cse = True

    def run(self, root: ir.Node, ctx: Context):
        self.key_to_node = {}
        self.bctx = []
        new_root = self.visit(root)
        return new_root

    def visit_(self, node: ir.Node):
        if node._key not in self.key_to_node:
            nc = self.visit_children(node)
            new_node = type(node)(*nc, **node.field_dict)
            assert new_node._key==node._key
            self.key_to_node[new_node._key] = new_node
        return self.key_to_node[node._key]
    
    def visit(self, node: ir.Node):
        return self.visit_(node)

    @handles(ir.Lambda)
    def _(self, node: ir.Lambda):
        lam_key = node._key
        self.bctx.append(lam_key)
        new_node = self.visit_(node)
        self.bctx.pop()
        return new_node

    @handles(ir.LambdaT)
    def _(self, node: ir.LambdaT):
        lamT_key = node._key
        self.bctx.append(lamT_key)
        new_node = self.visit_(node)
        self.bctx.pop()
        return new_node

    @handles(ir.BoundVar)
    def _(self, node: ir.BoundVar):
        key = (self.bctx[-(node.idx+1)], node._key)
        if key not in self.key_to_node:
            self.key_to_node[key] = node
        return self.key_to_node[key]