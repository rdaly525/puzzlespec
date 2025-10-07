from ast import Pass
from multiprocessing import Value
import typing as tp

from puzzlespec.compiler.passes.analyses import sym_table
from . import ast, ir, ir_types as irT
from .topology import Topology, Grid2D
from dataclasses import dataclass

from ..passes.pass_base import PassManager, Context, Transform, Analysis, AnalysisObject
from ..passes.analyses import SymTableEnv_
from ..passes.analyses.constraint_categorizer import ConstraintCategorizerVals, ConstraintCategorizer
from ..passes.transforms import SubstitutionPass, SubMapping, ConstFoldPass, ResolveBoundVars
from ..utils import pretty_print
from .envs import SymTable, TypeEnv, ShapeEnv

class PuzzleSpec:
    def __init__(self, name: str, desc: str, topo: Topology):
        self.name = name
        self.desc = desc
        self.topo = topo

        # Rules storage - separated by constraint type
        self._param_rules: ast.BoolExpr = ast.wrap(ir.Conj(), irT.Bool)
        self._gen_rules: ast.BoolExpr = ast.wrap(ir.Conj(), irT.Bool)
        self._decision_rules: ast.BoolExpr = ast.wrap(ir.Conj(), irT.Bool)


        # Environments
        self.sym = SymTable()
        self.tenv = TypeEnv()
        self.shape_env = ShapeEnv()

    # TODO
    def __repr__(self):
        return f"PuzzleSpec(name={self.name}, desc={self.desc}, topo={self.topo})"
    
    # Returns a dict of param names to param node
    @property
    def params(self) -> tp.Dict[str, ast.Expr]:
        return {self.sym.get_name(sid): ast.wrap(ir.VarRef(sid), self.tenv[sid]) for sid in self.sym.get_params()}

    # Returns a dict of gen var names to gen var node
    @property
    def gen_vars(self) -> tp.Dict[str, ast.Expr]:
        return {self.sym.get_name(sid): ast.wrap(ir.VarRef(sid), self.tenv[sid]) for sid in self.sym.get_gen_vars()}

    # Returns a dict of decision var names to decision var node
    @property
    def decision_vars(self) -> tp.Dict[str, ast.Expr]:
        return {self.sym.get_name(sid): ast.wrap(ir.VarRef(sid), self.tenv[sid]) for sid in self.sym.get_decision_vars()}

    @property
    def param_constraints(self) -> ast.BoolExpr:
        return self._param_rules

    @property
    def gen_constraints(self) -> ast.BoolExpr:
        return self._gen_rules

    @property
    def decision_constraints(self) -> ast.BoolExpr:
        return self._decision_rules

    @property
    def constant_constraints(self) -> ast.BoolExpr:
        # For now, return empty Conj since we don't support constant constraints yet
        return ast.wrap(ir.Conj(), irT.Bool)

    @property
    def rules(self) -> ast.BoolExpr:
        # Return predictable structure: Conj(param_rules, gen_rules, decision_rules)
        # Always include all three rule types, even if empty
        return ast.wrap(ir.Conj(
            self._param_rules.node,
            self._gen_rules.node, 
            self._decision_rules.node
        ), irT.Bool)

    # TODO
    # Returns a new spec with the params set
    def set_params(self, **kwargs) -> 'PuzzleSpec':
        new_spec = ...
        
        # Run parameter substitution and constant propagation
        ctx = Context()
        ctx.add(ParamValues(**kwargs))
        pm = PassManager(ParamSubPass(), ConstPropPass())
        
        # Transform each rule type separately
        new_spec._param_rules = self._transform_rule_list(new_spec._param_rules, pm, ctx)
        new_spec._gen_rules = self._transform_rule_list(new_spec._gen_rules, pm, ctx)  
        new_spec._decision_rules = self._transform_rule_list(new_spec._decision_rules, pm, ctx)
        
        # Validate parameter constraints - much simpler now!
        self._validate_param_constraints(new_spec._param_rules, kwargs)
        
        # Apply to topology dimensions
        if isinstance(new_spec.topo, Grid2D):
            new_nR = ast.wrap(pm.run(new_spec.topo.nR.node, ctx), irT.Int)
            new_nC = ast.wrap(pm.run(new_spec.topo.nC.node, ctx), irT.Int)
            new_spec.topo = Grid2D(new_nR, new_nC)
        
        return new_spec.freeze()

    def _transform_rule_list(self, rule_list: ast.BoolExpr, pm: PassManager, ctx: Context) -> ast.BoolExpr:
        """Transform each child of a rule list independently."""
        assert isinstance(rule_list.node, ir.Conj), f"Expected Conj node, got {type(rule_list.node)}"
        
        if len(rule_list.node._children) == 0:
            # Empty rule list stays empty
            return rule_list
        
        # Transform each child independently
        transformed_children = []
        for child in rule_list.node._children:
            transformed_child = pm.run(child, ctx)
            transformed_children.append(transformed_child)
        
        # Reconstruct the rule list
        return ast.wrap(ir.Conj(*transformed_children), irT.Bool)

    def _validate_param_constraints(self, transformed_param_rules: ast.BoolExpr, param_values: tp.Dict[str, tp.Any]):
        """Validate that parameter values satisfy the parameter constraints."""
        # After transformation, the rules might be simplified to a single literal
        if isinstance(transformed_param_rules.node, ir.Lit):
            # If it's a literal False, all constraints were violated
            if transformed_param_rules.node.value is False:
                # Get original parameter constraints for error message
                original_param_rules = self._param_rules
                assert isinstance(original_param_rules.node, ir.Conj), f"Expected Conj node for original param constraints"
                original_constraints = original_param_rules.node._children
                self._raise_param_constraint_error_with_printer(original_constraints, param_values)
            # If it's literal True, all constraints are satisfied
            return
        
        # The transformed parameter rules should be a Conj node
        assert isinstance(transformed_param_rules.node, ir.Conj), f"Expected Conj node for param constraints, got {type(transformed_param_rules.node)}"
        
        if len(transformed_param_rules.node._children) == 0:
            # No parameter constraints to validate
            return
        
        # Get original parameter constraints for pretty printing
        original_param_rules = self._param_rules
        assert isinstance(original_param_rules.node, ir.Conj), f"Expected Conj node for original param constraints"
        original_constraints = original_param_rules.node._children
        
        # Check each transformed parameter constraint against its original
        violated_original_constraints = []
        transformed_constraints = transformed_param_rules.node._children
        
        for i, transformed_node in enumerate(transformed_constraints):
            # After parameter substitution and constant propagation, this could be:
            # - A literal (fully resolved): check if False
            # - A non-literal (partially resolved): allow it (partial evaluation)
            if isinstance(transformed_node, ir.Lit):
                if transformed_node.value is False:
                    # This specific constraint was violated - get the original constraint
                    if i < len(original_constraints):
                        violated_original_constraints.append(original_constraints[i])
            # If not a literal, it means some parameters are unresolved - that's OK for partial evaluation
        
        # If any constraints were violated, raise an error with pretty-printed original constraints
        if violated_original_constraints:
            self._raise_param_constraint_error_with_printer(violated_original_constraints, param_values)

    def _raise_param_constraint_error_with_printer(self, violated_nodes: tp.List[ir.Node], param_values: tp.Dict[str, tp.Any]):
        """Raise a helpful error message for violated constraints."""
        
        param_str = ", ".join(f"{k}={v}" for k, v in param_values.items())
        
        # Create error messages for each violated constraint
        error_messages = []
        for node in violated_nodes:
            try:
                # Use pretty printer to show the original constraint
                constraint_desc = pretty_print(node)
            except Exception:
                # Fallback if pretty printing fails
                constraint_desc = str(node)
            
            error_messages.append(f"The constraint {constraint_desc} is violated when {param_str}")
        
        # Join multiple violations with newlines
        full_message = "\n".join(error_messages)
        raise ValueError(full_message)