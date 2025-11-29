from ..pass_base import Transform, Context, AnalysisObject, handles
from ...dsl import ir
import typing as tp
from dataclasses import dataclass

@dataclass
class SubMappingEntry:
    match: tp.Callable
    replace: tp.Callable

class SubMapping(AnalysisObject):
    def __init__(self):
        self.mappings = []

    def add(self, match:tp.Callable, replace:tp.Callable):
        self.mappings.append(SubMappingEntry(match, replace))

    def __iter__(self):
        return iter(self.mappings)

class SubstitutionPass(Transform):
    requires = (SubMapping,)
    produces = ()
    name = "substitution"

    def run(self, root: ir.Node, ctx: Context):
        self.sub_mapping = ctx.get(SubMapping)
        return self.visit(root)
    
    # TODO inefficient
    def visit(self, node: ir.Node):
        for submap in self.sub_mapping:
            if submap.match(node):
                return submap.replace(node)
        new_children = self.visit_children(node)
        return node.replace(*new_children)