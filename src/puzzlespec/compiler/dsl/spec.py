import typing as tp
from . import ast, ir, ir_types as irT
from .topology import Topology
from dataclasses import dataclass

from ..passes import PassManager, Context, Transform, Analysis, AnalysisObject


class TypeEnv:
    def __init__(self):
        self.vars = {}

    def __getitem__(self, name: str) -> irT.Type_:
        return self.vars.get(name, None)
    
    def add(self, name: str, sort: irT.Type_):
        if name in self.vars:
            raise ValueError(f"Variable {name} already defined")
        self.vars[name] = sort

class RoleEnv:
    def __init__(self):
        self.roles: tp.Dict[str, str] = {}

    def __getitem__(self, name: str) -> str:
        return self.roles.get(name, None)

    def add(self, name: str, role: str):
        # last write wins; roles can be updated when variables are concretized
        self.roles[name] = role

class PuzzleSpec:
    def __init__(self, name: str, desc: str, topo: Topology):
        self.name = name
        self.desc = desc
        self.topo = topo
        self._frozen = False
        self._all_rules: ast.BoolExpr = ast.wrap(ir.Conj(), irT.Bool)  # Empty Conj
        self._var_name_cnt = 0

        # Environment - still needed for variable creation and type tracking
        self.tenv = TypeEnv()
        self.renv = RoleEnv()

        # Cache for derived values (cleared when rules or environments change)
        self._derived_cache = None

    def _clear_cache(self):
        """Clear the derived values cache when rules or environments change."""
        self._derived_cache = None

    def _get_derived_values(self):
        """Run analysis passes to derive values from rules. Results are cached."""
        if self._derived_cache is not None:
            return self._derived_cache
        
        # Run the analysis passes to extract information from rules
        from ..passes.analyses import Getter, ConstraintSorter, RoleEnv_
        from ..passes.analyses.getter import GetterVals
        from ..passes.analyses.constraint_sorter import ConstraintSorterVals
        
        ctx = Context()
        ctx.add(self.tenv)
        ctx.add(RoleEnv_(self.renv))
        
        pm = PassManager(
            Getter(),
            ConstraintSorter()
        )
        
        pm.run(self._all_rules.node, ctx)
        getter_vals = ctx.get(GetterVals)
        sorter_vals = ctx.get(ConstraintSorterVals)
        
        # Wrap the extracted values
        params = {}
        for name, node in getter_vals.param_vals.items():
            # Parameters are always Int type
            params[name] = ast.wrap(node, irT.Int)
        
        gen_vars = {}
        for name, node in getter_vals.gen_vals.items():
            var_type = self.tenv[name]
            if var_type is None:
                raise ValueError(f"Gen var {name} not found in type environment")
            gen_vars[name] = ast.wrap(node, var_type)
        
        decision_vars = {}
        for name, node in getter_vals.decision_vals.items():
            var_type = self.tenv[name]
            if var_type is None:
                raise ValueError(f"Decision var {name} not found in type environment")
            decision_vars[name] = ast.wrap(node, var_type)
        
        # Wrap constraint categories
        param_constraints = ast.wrap(ir.Conj(*sorter_vals.param_constraints), irT.Bool)
        gen_constraints = ast.wrap(ir.Conj(*sorter_vals.gen_constraints), irT.Bool)
        decision_constraints = ast.wrap(ir.Conj(*sorter_vals.decision_constraints), irT.Bool)
        constant_constraints = ast.wrap(ir.Conj(*sorter_vals.constant_constraints), irT.Bool)
        
        derived_values = {
            'params': params,
            'gen_vars': gen_vars,
            'decision_vars': decision_vars,
            'param_constraints': param_constraints,
            'gen_constraints': gen_constraints,
            'decision_constraints': decision_constraints,
            'constant_constraints': constant_constraints
        }
        
        self._derived_cache = derived_values
        return derived_values

    def __iadd__(self, other):
        if self.is_frozen():
            raise ValueError("Cannot add rules to a frozen spec")
        
        # Convert other to BoolExpr
        if isinstance(other, tp.Iterable) and not isinstance(other, (str, ast.Expr)):
            # Handle iterable of constraints
            new_constraints = [ast.BoolExpr.make(o) for o in other]
        else:
            # Handle single constraint
            new_constraints = [ast.BoolExpr.make(other)]
        
        # Check if current rules is an empty Conj
        if isinstance(self._all_rules.node, ir.Conj) and len(self._all_rules.node._children) == 0:
            # Replace empty Conj with new constraints
            self._all_rules = ast.BoolExpr.all_of(*new_constraints)
        else:
            # Extract existing constraints from the current Conj and add new ones
            existing_constraints = [ast.wrap(child, irT.Bool) for child in self._all_rules.node._children]
            all_constraints = existing_constraints + new_constraints
            self._all_rules = ast.BoolExpr.all_of(*all_constraints)
        
        # Clear cache since rules have changed
        self._clear_cache()
        return self

    def _new_var_name(self):
        self._var_name_cnt += 1
        return f"v{self._var_name_cnt}"

    def __repr__(self):
        return f"PuzzleSpec(name={self.name}, desc={self.desc}, topo={self.topo})"
    
    def get_var(self, name: str) -> tp.Optional[ast.Expr]:
        # Look up variable from derived values
        derived = self._get_derived_values()
        if name in derived['gen_vars']:
            return derived['gen_vars'][name]
        elif name in derived['decision_vars']:
            return derived['decision_vars'][name]
        else:
            raise ValueError(f"Variable {name} not defined")

    def var_dict(self, keys: ast.ListExpr[ast.Expr], sort: irT.Type_, name: str, gen: bool=False) -> ast.DictExpr[ast.Expr, irT.Type_]:
        if self.is_frozen():
            raise ValueError("Cannot create variables in a frozen spec")
        if name in self.tenv.vars:
            raise ValueError(f"Variable with name {name} already defined in type environment")
        if name in self.renv.roles:
            raise ValueError(f"Variable with name {name} already defined in role environment")
        node = ir.VarDict(keys.node, name)
        T = irT.DictT(keys.elem_type, sort)
        expr = tp.cast(ast.DictExpr[ast.Expr, irT.Type_], ast.wrap(node, T))
        self.tenv.add(name, T)
        role = 'G' if gen else 'D'
        self.renv.add(name, role)
        self._clear_cache()  # Clear cache since environments changed
        return expr
    
    def var_list(self, size: ast.IntExpr, sort: irT.Type_, role: str = 'decision', name: tp.Optional[str] = None) -> ast.ListExpr[irT.Type_]:
        if self.is_frozen():
            raise ValueError("Cannot create variables in a frozen spec")
        if name is None:
            name = self._new_var_name()
        node = ir.VarList(size.node, name)
        T = irT.ListT(sort)
        expr = tp.cast(ast.ListExpr[ast.Expr], ast.wrap(node, T))
        self.tenv.add(name, T)
        self.renv.add(name, role)
        self._clear_cache()  # Clear cache since environments changed
        return expr
    
    def var(self, sort: irT.Type_, role: str = 'decision', name: tp.Optional[str] = None) -> ast.Expr:
        if self.is_frozen():
            raise ValueError("Cannot create variables in a frozen spec")
        if name is None:
            name = self._new_var_name()
        v = ast.wrap(ir.FreeVar(name), sort)
        self.tenv.add(name, sort)
        self.renv.add(name, role)
        self._clear_cache()  # Clear cache since environments changed
        return v

    # Freezes the spec and makes it immutable (no new rules can be added).
    def freeze(self):
        self._frozen = True
        return self

    def is_frozen(self):
        return self._frozen

    # Returns a dict of param names to param node
    @property
    def params(self) -> tp.Dict[str, ast.Expr]:
        return self._get_derived_values()['params']

    # Returns a dict of gen var names to gen var node
    @property
    def gen_vars(self) -> tp.Dict[str, ast.Expr]:
        return self._get_derived_values()['gen_vars']

    # Returns a dict of decision var names to decision var node
    @property
    def decision_vars(self) -> tp.Dict[str, ast.Expr]:
        return self._get_derived_values()['decision_vars']

    @property
    def param_constraints(self) -> ast.BoolExpr:
        return self._get_derived_values()['param_constraints']

    @property
    def gen_constraints(self) -> ast.BoolExpr:
        return self._get_derived_values()['gen_constraints']

    @property
    def decision_constraints(self) -> ast.BoolExpr:
        return self._get_derived_values()['decision_constraints']

    @property
    def constant_constraints(self) -> ast.BoolExpr:
        return self._get_derived_values()['constant_constraints']

    @property
    def rules(self) -> ast.BoolExpr:
        return self._all_rules

    # Returns a new spec with the params set
    def set_params(self, **kwargs) -> 'PuzzleSpec':
        if not self.is_frozen():
            raise NotImplementedError("Spec must be frozen to set params")
        new_spec = _copy_spec(self, freeze=False)
        
        # Run the param substitution pass on the rules
        from ..passes.transforms import ParamSubPass, ParamValues
        ctx = Context()
        ctx.add(ParamValues(**kwargs))
        pm = PassManager(
            ParamSubPass()
        )
        
        # Apply parameter substitution to the rules only
        # Variables will be derived from the transformed rules
        new_rules_node = pm.run(new_spec._all_rules.node, ctx)
        new_spec._all_rules = ast.wrap(new_rules_node, irT.Bool)
        
        # Freeze the new spec
        return new_spec.freeze()

def _copy_spec(spec: 'PuzzleSpec', freeze: bool = True) -> 'PuzzleSpec':
    """Create a deep copy of a frozen spec."""
    if not spec.is_frozen():
        raise ValueError("Can only copy frozen specs")
    
    # Create a new spec with the same basic properties
    new_spec = PuzzleSpec(spec.name, spec.desc, spec.topo)
    
    # Copy the rules using the Copy pass in spec mode
    from ..passes.analyses.copy import CopyPass, CopyResult, SourceSpec_, TargetSpec_
    copy_pass = CopyPass(mode="spec")
    ctx = Context()
    
    # Add source and target specs to context
    ctx.add(SourceSpec_(spec))
    ctx.add(TargetSpec_(new_spec))
    
    # Copy the full constraint tree
    copy_result: CopyResult = copy_pass.run(spec.rules.node, ctx)
    
    # Add the copied constraints to the new spec
    new_spec += ast.wrap(copy_result.copied_root, irT.Bool)
    
    # Freeze the new spec
    if freeze:
        new_spec.freeze()
    
    return new_spec