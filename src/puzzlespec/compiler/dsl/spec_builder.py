from ast import Pass
from multiprocessing import Value
from platform import python_version_tuple
import typing as tp

from . import ast, ir, ir_types as irT
from .topology import Topology, Grid2D
from .envs import SymTable, ShapeEnv, TypeEnv
from ..passes.canonicalize import canonicalize, _canonicalize
from ..passes.pass_base import PassManager, Context
from ..passes.analyses import SymTableEnv_
from ..passes.transforms.cse import CSE
from ..passes.analyses.constraint_categorizer import ConstraintCategorizerVals, ConstraintCategorizer
from ..passes.analyses.type_inference import TypeInferencePass, TypeEnv_, TypeValues
from ..passes.transforms import SubstitutionPass, SubMapping, ConstFoldPass, ResolveBoundVars
from ..utils import pretty_print
from .spec import PuzzleSpec
from ..passes.utils import printAST

class PuzzleSpecBuilder:
    def __init__(self, name: str, desc: str, topo: Topology):
        self.name = name
        self.desc = desc
        self.topo = topo
        self._frozen = False

        # Rules storage - separated by constraint type
        self._rules: ir.List = ir.List()
        
        # Environments
        self.sym = SymTable()
        self.tenv = TypeEnv()
        self.shape_env = ShapeEnv()

        self._name_name_cnt = 0


        # Params are declared before intiializing Builder.
        # During the Builder lifetime, these are stored in _params
        # Register these used parameters from topo
        self._params = {}
        self._register_params(*topo.terms())

    def _register_params(self, *terms: ir.Node):
        pm = PassManager(
            ConstraintCategorizer(include_params=True)
        )
        for term in terms:
            # New context for each constraint
            ctx = Context()
            ctx.add(SymTableEnv_(self.sym))
            pm.run(term, ctx) 
            ccvals = tp.cast(ConstraintCategorizerVals, ctx.get(ConstraintCategorizerVals))
            for pname, T in ccvals._params.items():
                if pname in self._params and T != self._params[pname]:
                    raise ValueError(f"param {pname} already exists")
                self._params[pname] = T


    def _new_var_name(self):
        self._var_name_cnt += 1
        return f"x{self._var_name_cnt}"

    def __repr__(self):
        return f"PuzzleSpec(name={self.name}, desc={self.desc}, topo={self.topo})"
    
    def _create_var(self, sort: irT.Type_, role: str, name: tp.Optional[str] = None) -> ast.Expr:
        if name is None:
            name = self._new_var_name()
        assert role in "GDP"
        sid = self.sym.new_var(name, role)
        v = canonicalize(ast.wrap(ir.VarRef(sid), sort))
        self.tenv.add(sid, sort)
        return sid, v

    def var(self, sort: irT.Type_, gen: bool=False, name: tp.Optional[str] = None) -> ast.Expr:
        role = "G" if gen else "D"
        sid, v = self._create_var(sort, role, name)
        self.shape_env.add_elem(sid)
        return v

    def var_list(self, size: ast.IntExpr, sort: irT.Type_, gen: bool=False, name: tp.Optional[str] = None) -> ast.ListExpr[irT.Type_]:
        role = "G" if gen else "D"
        varT = irT.ListT(sort)
        sid, v = self._create_var(varT, role, name)
        self.shape_env.add_list(sid, size=size)
        return v

    def var_dict(self, keys: ast.ListExpr[ast.Expr], sort: irT.Type_, name: str, gen: bool=False) -> ast.DictExpr[ast.Expr, irT.Type_]:
        role = "G" if gen else "D"
        varT = irT.DictT(keys.elem_type, sort)
        sid, v = self._create_var(varT, role, name)
        self.shape_env.add_dict(sid, keys=keys)
        return v

    def _replace_rules(self, new_rules: ir.Node):
        canon = _canonicalize(new_rules)
        self._rules = canon
 
    def _add_rules(self, *new_rules: ast.Expr):
        nodes = [*self._rules._children, *[r.node for r in new_rules]]
        self._replace_rules(ir.List(*nodes))

    def __iadd__(self, other):
        
        constraints = other
        if not isinstance(other, tp.Iterable):
            constraints = [other]

        # Verify that all the constraints bool expressions    
        if not all(isinstance(c, ast.BoolExpr) for c in constraints):
            raise ValueError(f"Constraints, {constraints}, is not a BoolExpr")
        
        # For every constraint:

        self._add_rules(*constraints)
        print("After adding rules")
        print(printAST(self._rules))
        # Extract all Parameters and add to sym table if they do not already exist
        self._register_params(self._rules)

        #  2: Resolve Placeholders (for bound bars/lambdas)
        # This will also implicitly do CSE as will any transformation pass
        pm = PassManager(ResolveBoundVars(), CSE())
        self._replace_rules(pm.run(self._rules))
        print("After resolving bound vars")
        print(printAST(self._rules))
        self._type_check()
        print(self.pretty())
        return self

   
    def _type_check(self):
        pm = PassManager(TypeInferencePass())
        ctx = Context()
        ctx.add(TypeEnv_(self.tenv))
        pm.run(self._rules, ctx)
        tvals = ctx.get(TypeValues).mapping
        if tvals[self._rules] != irT.ListT(irT.Bool):
            for c in self._rules._children:
                if tvals[c] != irT.Bool:
                    raise ValueError(f"Constraint {c} is not bool, {tvals[c]}")

    def _unify_params(self):
        smap = SubMapping()
        for pname, T in self._params.items():
            sid, v = self._create_var(T, 'P', pname)
            smap.add(
                match=lambda node: isinstance(node, ir._Param) and node.name==pname,
                replace=lambda node: ir.VarRef(sid)
            )
        pm = PassManager(SubstitutionPass())
        ctx = Context()
        ctx.add(smap)
        self._replace_rules(pm.run(self._rules, ctx))

    # Freezes the spec and makes it immutable (no new rules can be added).
    def build(self) -> PuzzleSpec:
        self._unify_params()
        print("After unifying params")
        print(printAST(self._rules))
        self._type_check()
        # Print AST
        print(self.pretty(self._rules))
        # 2) Run simplification loop
        # 3) Fold/invalidate the shape_env
        #   - Replace any Len(Var) with the shape_env size
        #   - Replace any Keys(Var) with shape_env keys
        # DO type checking/shape validation
        # Extract implicit constraints
        return self
    
    def pretty(self, constraint: ir.Node=None) -> str:
        """Pretty print a constraint using the spec's type environment."""
        from ..passes.analyses.pretty_printer import PrettyPrinterPass, PrettyPrintedExpr
        from ..passes.analyses.type_inference import TypeInferencePass, TypeEnv_
        from ..passes.pass_base import Context, PassManager
        
        if constraint is None:
            constraint = self._rules

        ctx = Context()
        ctx.add(TypeEnv_(self.tenv))
        ctx.add(SymTableEnv_(self.sym))
        pm = PassManager(
            TypeInferencePass(),
            PrettyPrinterPass()
        )
        # Run all passes and get the final result
        pm.run(constraint, ctx)
        
        # Get the pretty printed result from context
        result = ctx.get(PrettyPrintedExpr)
        return result.text

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
        return self._rules