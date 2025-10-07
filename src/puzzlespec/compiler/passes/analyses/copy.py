from ..pass_base import Context, AnalysisObject, Analysis, handles
from ...dsl import ir
import typing as tp

class CopyResult(AnalysisObject):
    """Stores the deep copied root node."""
    def __init__(self, copied_root: ir.Node):
        self.copied_root = copied_root

class CopyPass(Analysis):
    """Analysis pass that creates a deep copy of the root node.
    """   
    produces = (CopyResult,)
    name = "copy"
    
    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.node_mapping = {}
        copied_root = self.visit(root)
        ctx.add(CopyResult(copied_root))
        return root

    def visit(self, node: ir.Node) -> ir.Node:
        """Default visit method that performs deep copy."""
        # If we've already copied this node, return the copy
        if node in self.node_mapping:
            return self.node_mapping[node]
        
        # Copy all children first
        copied_children = tuple(self.visit(child) for child in node._children)
        copied_node = node.replace(*copied_children)
        
        # Store the mapping for potential reuse
        self.node_mapping[node] = copied_node
        return copied_node