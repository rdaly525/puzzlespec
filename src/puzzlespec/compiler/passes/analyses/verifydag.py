from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir

class Aobj(AnalysisObject): pass

class VerifyDag(Analysis):
    name = "verify_dag"
    #enable_memoization=False

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        self.stack = []
        self.visit(root)
        return Aobj()

    def visit(self, node: ir.Node):
        if node in self.stack:
            raise ValueError()
        self.stack.append(node)
        self.visit_children(node)
        self.stack.pop()