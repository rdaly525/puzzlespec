"""Utility functions for the compiler module."""

def pretty_print(constraint) -> str:
    """Pretty print a constraint using the PrettyPrinterPass."""
    from .passes.analyses.pretty_printer import PrettyPrinterPass, PrettyPrintedExpr
    from .passes.analyses.type_inference import TypeInferencePass, TypeEnv_
    from .passes.analyses.scope_analysis import ScopeAnalysisPass
    from .dsl import ast, ir_types as irT
    from .dsl.spec import TypeEnv
    from .passes.pass_base import Context, PassManager
    
    # Wrap the constraint as an ast.Expr if it's an ir.Node
    if hasattr(constraint, '_children'):  # It's an ir.Node
        constraint_expr = ast.wrap(constraint, irT.Bool)
    else:
        constraint_expr = constraint
    
    # Set up context with required dependencies
    ctx = Context()
    
    # Add empty type environment to satisfy TypeInferencePass dependencies
    empty_tenv = TypeEnv()
    ctx.add(TypeEnv_(empty_tenv))
    
    # Use PassManager to run the analysis passes in the correct order
    pm = PassManager(
        TypeInferencePass(),
        ScopeAnalysisPass(),
        PrettyPrinterPass()
    )
    
    # Run all passes and get the final result
    pm.run(constraint_expr.node, ctx)
    
    # Get the pretty printed result from context
    result = ctx.get(PrettyPrintedExpr)
    return result.text
