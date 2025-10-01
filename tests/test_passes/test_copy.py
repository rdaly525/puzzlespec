import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

try:
    import pytest
except ImportError:
    # Mock pytest for environments without it
    class MockPytest:
        @staticmethod
        def raises(exception_type, **kwargs):
            class ContextManager:
                def __init__(self, exc_type):
                    self.exc_type = exc_type
                def __enter__(self): 
                    return self
                def __exit__(self, exc_type, exc_val, exc_tb):
                    if exc_type is None:
                        raise AssertionError(f"Expected {self.exc_type.__name__} but no exception was raised")
                    return isinstance(exc_val, self.exc_type)
            return ContextManager(exception_type)
    pytest = MockPytest()

from puzzlespec import get_puzzle
from puzzlespec.compiler.dsl import ir, ir_types as irT, ast
from puzzlespec.compiler.passes import Context, PassManager, analyses as A
from puzzlespec.compiler.passes.analyses.copy import CopyPass, CopyResult, SourceSpec_, TargetSpec_
from puzzlespec.compiler.dsl.spec import PuzzleSpec, _copy_spec
from puzzlespec.compiler.dsl.topology import Grid2D


def test_copy_pass_basic_mode():
    """Test CopyPass in basic mode with simple IR tree."""
    # Create a simple IR tree
    root = ir.And(
        ir.Lit(True),
        ir.Or(ir.Lit(False), ir.Lit(42))
    )
    
    # Run copy pass in basic mode
    ctx = Context()
    copy_pass = CopyPass(mode="basic")
    result = copy_pass.run(root, ctx)
    
    # Verify result
    assert isinstance(result, CopyResult)
    copied_root = result.copied_root
    
    # Should be different objects
    assert root is not copied_root
    assert root._children[0] is not copied_root._children[0]
    assert root._children[1] is not copied_root._children[1]
    
    # Should have same structure and values
    assert type(root) == type(copied_root)
    assert len(root._children) == len(copied_root._children)
    assert isinstance(copied_root._children[0], ir.Lit)
    assert copied_root._children[0].value is True
    assert isinstance(copied_root._children[1], ir.Or)


def test_copy_pass_basic_mode_with_shared_nodes():
    """Test CopyPass basic mode preserves sharing structure."""
    # Create tree with shared node
    shared_lit = ir.Lit(42)
    root = ir.And(shared_lit, ir.Or(shared_lit, ir.Lit(True)))
    
    # Verify original sharing
    assert root._children[0] is root._children[1]._children[0]
    
    # Run copy pass
    ctx = Context()
    copy_pass = CopyPass(mode="basic")
    result = copy_pass.run(root, ctx)
    copied_root = result.copied_root
    
    # Verify copied sharing is preserved
    assert copied_root._children[0] is copied_root._children[1]._children[0]
    # But different from original
    assert copied_root._children[0] is not shared_lit


def test_copy_pass_spec_mode_with_variables():
    """Test CopyPass in spec mode with variable reconstruction."""
    # Create source and target specs
    topo = Grid2D(3, 3)
    source_spec = PuzzleSpec('source', 'Source spec', topo)
    target_spec = PuzzleSpec('target', 'Target spec', topo)
    
    # Add variables to source spec
    x = source_spec.var(irT.Int, role='D', name='x')
    y = source_spec.var(irT.Int, role='D', name='y')
    
    # Create IR tree with variables
    root = ir.And(
        ir.Gt(ir.FreeVar('x'), ir.Lit(0)),
        ir.Lt(ir.FreeVar('y'), ir.FreeVar('x'))
    )
    
    # Set up context with specs
    ctx = Context()
    ctx.add(SourceSpec_(source_spec))
    ctx.add(TargetSpec_(target_spec))
    
    # Run copy pass in spec mode
    copy_pass = CopyPass(mode="spec")
    result = copy_pass.run(root, ctx)
    copied_root = result.copied_root
    
    # Verify variables were created in target spec
    assert 'x' in target_spec._exprs
    assert 'y' in target_spec._exprs
    
    # Verify copied tree uses target spec variables
    assert copied_root is not root
    # The copied variables should be from target spec
    copied_x_node = copied_root._children[0]._children[0]  # First Gt's first child
    copied_y_node = copied_root._children[1]._children[0]  # Second Lt's first child
    
    assert isinstance(copied_x_node, ir.FreeVar)
    assert isinstance(copied_y_node, ir.FreeVar)
    assert copied_x_node.name == 'x'
    assert copied_y_node.name == 'y'


def test_copy_pass_spec_mode_missing_dependencies():
    """Test CopyPass spec mode fails without required dependencies."""
    root = ir.Lit(True)
    ctx = Context()  # Empty context
    
    copy_pass = CopyPass(mode="spec")
    
    with pytest.raises(KeyError):
        copy_pass.run(root, ctx)


def test_copy_pass_invalid_mode():
    """Test CopyPass rejects invalid modes."""
    with pytest.raises(ValueError, match="Invalid mode: invalid"):
        CopyPass(mode="invalid")


def test_copy_pass_with_var_list():
    """Test CopyPass spec mode with VarList variables."""
    topo = Grid2D(2, 2)
    source_spec = PuzzleSpec('source', 'Source spec', topo)
    target_spec = PuzzleSpec('target', 'Target spec', topo)
    
    # Add VarList to source spec
    size = source_spec.var(irT.Int, role='D', name='size')
    bool_list = source_spec.var_list(size, irT.Bool, role='D', name='bool_list')
    
    # Create IR tree with VarList
    root = ir.Eq(
        ir.ListLength(ir.VarList(ir.FreeVar('size'), 'bool_list')),
        ir.FreeVar('size')
    )
    
    # Set up context
    ctx = Context()
    ctx.add(SourceSpec_(source_spec))
    ctx.add(TargetSpec_(target_spec))
    
    # Run copy pass
    copy_pass = CopyPass(mode="spec")
    result = copy_pass.run(root, ctx)
    
    # Verify variables were created in target spec
    assert 'size' in target_spec._exprs
    assert 'bool_list' in target_spec._exprs
    
    # Verify types are preserved
    assert target_spec.tenv['size'] == irT.Int
    assert isinstance(target_spec.tenv['bool_list'], irT.ListT)
    assert target_spec.tenv['bool_list'].elemT == irT.Bool


def test_copy_spec_function():
    """Test the _copy_spec function end-to-end."""
    # Create and set up original spec
    topo = Grid2D(3, 3)
    spec = PuzzleSpec('original', 'Original spec', topo)
    
    # Add variables
    x = spec.var(irT.Int, role='D', name='x')
    y = spec.var(irT.Int, role='D', name='y')
    size = spec.var(irT.Int, role='D', name='size')
    bool_list = spec.var_list(size, irT.Bool, role='D', name='bool_list')
    
    # Add constraints
    spec += (x > 0)
    spec += (y > x)
    spec += (bool_list.__len__() == size)
    
    # Freeze original spec
    spec.freeze()
    
    # Copy the spec
    copied_spec = _copy_spec(spec)
    
    # Verify basic properties
    assert copied_spec.name == spec.name
    assert copied_spec.desc == spec.desc
    assert copied_spec is not spec
    assert copied_spec.is_frozen()
    
    # Verify variables were copied
    assert set(spec.decision_vars.keys()) == set(copied_spec.decision_vars.keys())
    
    # Verify variables are different objects
    for var_name in spec.decision_vars.keys():
        orig_var = spec.decision_vars[var_name]
        copied_var = copied_spec.decision_vars[var_name]
        assert orig_var is not copied_var
        
        # But names should be preserved (check the underlying nodes)
        if hasattr(orig_var.node, 'name') and hasattr(copied_var.node, 'name'):
            assert orig_var.node.name == copied_var.node.name
    
    # Verify type environments are equivalent but separate
    assert spec.tenv.vars == copied_spec.tenv.vars
    assert spec.tenv is not copied_spec.tenv
    
    # Verify that variables are now ast.Expr objects, not raw nodes
    for var_name in spec.decision_vars.keys():
        orig_var = spec.decision_vars[var_name]
        copied_var = copied_spec.decision_vars[var_name]
        assert isinstance(orig_var, ast.Expr), f"Original {var_name} should be ast.Expr, got {type(orig_var)}"
        assert isinstance(copied_var, ast.Expr), f"Copied {var_name} should be ast.Expr, got {type(copied_var)}"


def test_copy_spec_unfrozen_rejection():
    """Test that _copy_spec rejects unfrozen specs."""
    topo = Grid2D(2, 2)
    unfrozen_spec = PuzzleSpec('unfrozen', 'Unfrozen spec', topo)
    
    with pytest.raises(ValueError, match="Can only copy frozen specs"):
        _copy_spec(unfrozen_spec)


def test_spec_variables_are_ast_expr():
    """Test that spec variables are stored as ast.Expr objects after freezing."""
    topo = Grid2D(3, 3)
    spec = PuzzleSpec('test_expr', 'Test ast.Expr storage', topo)
    
    # Add different types of variables
    x = spec.var(irT.Int, role='D', name='x')
    y_list = spec.var_list(spec.var(irT.Int, role='D', name='size'), irT.Bool, role='D', name='y_list')
    
    # Add a constraint to ensure we have something to freeze
    spec += (x > 0)
    
    # Freeze the spec
    spec.freeze()
    
    # Verify all variables are ast.Expr objects
    for var_name, var_expr in spec.decision_vars.items():
        assert isinstance(var_expr, ast.Expr), f"Decision var {var_name} should be ast.Expr, got {type(var_expr)}"
        assert hasattr(var_expr, 'node'), f"Decision var {var_name} should have .node attribute"
        assert hasattr(var_expr, 'T'), f"Decision var {var_name} should have .T attribute"
    
    # If there were params, they should also be ast.Expr
    for var_name, var_expr in spec.params.items():
        assert isinstance(var_expr, ast.Expr), f"Param {var_name} should be ast.Expr, got {type(var_expr)}"
    
    # If there were gen vars, they should also be ast.Expr  
    for var_name, var_expr in spec.gen_vars.items():
        assert isinstance(var_expr, ast.Expr), f"Gen var {var_name} should be ast.Expr, got {type(var_expr)}"


def test_copy_pass_with_complex_puzzle():
    """Test CopyPass with a real puzzle spec."""
    # Get a real puzzle
    spec = get_puzzle("unruly")
    
    # Test basic mode on rules
    ctx = Context()
    copy_pass = CopyPass(mode="basic")
    result = copy_pass.run(spec.rules.node, ctx)
    
    # Should successfully copy without errors
    assert isinstance(result, CopyResult)
    assert result.copied_root is not spec.rules.node
    
    # Test full spec copy
    copied_spec = _copy_spec(spec)
    assert copied_spec is not spec
    assert copied_spec.is_frozen()
    assert set(spec.decision_vars.keys()) == set(copied_spec.decision_vars.keys())
    
    # Verify variables are ast.Expr objects in both specs
    for var_name in spec.decision_vars.keys():
        assert isinstance(spec.decision_vars[var_name], ast.Expr)
        assert isinstance(copied_spec.decision_vars[var_name], ast.Expr)


if __name__ == "__main__":
    # Run tests individually for debugging
    test_copy_pass_basic_mode()
    test_copy_pass_basic_mode_with_shared_nodes()
    test_copy_pass_spec_mode_with_variables()
    test_copy_pass_spec_mode_missing_dependencies()
    test_copy_pass_invalid_mode()
    test_copy_pass_with_var_list()
    test_copy_spec_function()
    test_copy_spec_unfrozen_rejection()
    test_spec_variables_are_ast_expr()
    test_copy_pass_with_complex_puzzle()
    print("All tests passed!")
