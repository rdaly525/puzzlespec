from ..pass_base import Context, AnalysisObject, Analysis, handles
from ...dsl import ir
import typing as tp

if tp.TYPE_CHECKING:
    from ...dsl.spec import PuzzleSpec


class CopyResult(AnalysisObject):
    """Stores the deep copied root node."""
    def __init__(self, copied_root: ir.Node):
        self.copied_root = copied_root


class SourceSpec_(AnalysisObject):
    """Wrapper for source spec in copy context."""
    def __init__(self, spec: 'PuzzleSpec'):
        self.spec = spec


class TargetSpec_(AnalysisObject):
    """Wrapper for target spec in copy context."""
    def __init__(self, spec: 'PuzzleSpec'):
        self.spec = spec


class CopyPass(Analysis):
    """Analysis pass that creates a deep copy of the root node.
    
    Two modes available:
    1. Basic mode: Simple deep copy without variable reconstruction
    2. Spec mode: Deep copy with variable reconstruction using source/target specs
    """
    produces = (CopyResult,)
    name = "copy"
    
    def __init__(self, mode: str = "basic"):
        """Initialize CopyPass with specified mode.
        
        Args:
            mode: Either "basic" for simple copying or "spec" for spec copying with variable reconstruction
        """
        super().__init__()
        self.node_mapping: tp.Dict[ir.Node, ir.Node] = {}
        self.mode = mode
        
        if mode == "basic":
            self.requires = ()
        elif mode == "spec":
            self.requires = (SourceSpec_, TargetSpec_)
        else:
            raise ValueError(f"Invalid mode: {mode}. Must be 'basic' or 'spec'")

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        """Run the copy pass on the root node."""
        self.node_mapping = {}
        
        if self.mode == "basic":
            # Basic mode: no context dependencies
            self.source_spec = None
            self.target_spec = None
        elif self.mode == "spec":
            # Spec mode: get required dependencies from context
            self.source_spec = ctx.get(SourceSpec_)
            self.target_spec = ctx.get(TargetSpec_)
        
        copied_root = self.visit(root)
        return CopyResult(copied_root)

    def visit(self, node: ir.Node) -> ir.Node:
        """Default visit method that performs deep copy."""
        # If we've already copied this node, return the copy
        if node in self.node_mapping:
            return self.node_mapping[node]
        
        # Copy all children first
        copied_children = tuple(self.visit(child) for child in node._children)
        
        # Create a copy of the current node with copied children
        # Use the node's _fields to preserve any additional attributes
        fields = {f: getattr(node, f) for f in node._fields}
        copied_node = type(node)(*copied_children, **fields)
        
        # Store the mapping for potential reuse
        self.node_mapping[node] = copied_node
        
        return copied_node

    @handles(ir.FreeVar, ir.VarList, ir.VarDict)
    def visit_variable_node(self, node: ir.Node) -> ir.Node:
        """Handle variable nodes that need to be reconstructed in target spec."""
        # If we've already copied this node, return the copy
        if node in self.node_mapping:
            return self.node_mapping[node]
        
        if self.target_spec is None or self.source_spec is None:
            # No target/source spec, just do regular copy using default behavior
            copied_children = tuple(self.visit(child) for child in node._children)
            fields = {f: getattr(node, f) for f in node._fields}
            copied_node = type(node)(*copied_children, **fields)
            self.node_mapping[node] = copied_node
            return copied_node
        
        # For variable nodes, recreate them in the target spec using type/role info
        if isinstance(node, (ir.FreeVar, ir.VarList, ir.VarDict)):
            var_name = node.name
            
            # Get type and role from source spec
            var_type = self.source_spec.spec.tenv[var_name]
            var_role = self.source_spec.spec.renv[var_name]
            
            if var_type is None or var_role is None:
                raise ValueError(f"Variable {var_name} not found in source spec environments")
            
            # Create a structural copy of the variable node (maintaining one-to-one mapping)
            # We'll register the variable in the target spec environments separately
            if isinstance(node, ir.FreeVar):
                copied_node = ir.FreeVar(var_name)
            elif isinstance(node, ir.VarList):
                # Copy the size expression first
                size_node = node._children[0]
                copied_size_node = self.visit(size_node)
                copied_node = ir.VarList(copied_size_node, var_name)
            elif isinstance(node, ir.VarDict):
                # Copy the keys expression first
                keys_node = node._children[0]
                copied_keys_node = self.visit(keys_node)
                copied_node = ir.VarDict(copied_keys_node, var_name)
            else:
                raise ValueError(f"Unknown variable node type: {type(node)}")
            
            # Register the variable in target spec environments if not already present
            if var_name not in self.target_spec.spec.tenv.vars:
                self.target_spec.spec.tenv.add(var_name, var_type)
                self.target_spec.spec.renv.add(var_name, var_role)
            
            self.node_mapping[node] = copied_node
            return copied_node
        
        # Fallback to regular copy if not a recognized variable type
        copied_children = tuple(self.visit(child) for child in node._children)
        fields = {f: getattr(node, f) for f in node._fields}
        copied_node = type(node)(*copied_children, **fields)
        self.node_mapping[node] = copied_node
        return copied_node