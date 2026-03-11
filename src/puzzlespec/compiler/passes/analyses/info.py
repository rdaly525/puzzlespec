from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir

def count(node: ir.Node, unique: bool) -> int:
    cls = CounterUnique if unique else CounterAll
    return cls()(node, Context()).cnt

class CountObj(AnalysisObject):
    def __init__(self, cnt: int):
        self.cnt = cnt

class CounterAll(Analysis):
    requires = ()
    produces = (CountObj,)
    name = f"count_all"
    enable_memoization = True

    def run(self, root: ir.Node, ctx: Context):
        cnt = self.visit(root)
        return CountObj(cnt)

    def visit(self, node: ir.Node):
        cnts = self.visit_children(node)
        return sum(cnts) + 1

class CounterUnique(Analysis):
    requires = ()
    produces = (CountObj,)
    name = f"count_unique"
    enable_memoization = True

    def run(self, root: ir.Node, ctx: Context):
        self.cnt = 0
        self.visit(root)
        return CountObj(self.cnt)

    def visit(self, node: ir.Node):
        self.visit_children(node)
        self.cnt +=1

