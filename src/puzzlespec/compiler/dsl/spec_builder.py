from ast import Pass
import typing as tp

from . import ast, ir, ir_types as irT
from .topology import Topology
from .envs import SymTable, ShapeEnv, TypeEnv
from ..passes.pass_base import PassManager, Context
from ..passes.analyses import SymTableEnv_
from ..passes.transforms.cse import CSE
from ..passes.analyses.constraint_categorizer import ConstraintCategorizerVals, ConstraintCategorizer
from ..passes.analyses.type_inference import TypeInferencePass, TypeEnv_, TypeValues
from ..passes.analyses.getter import ParamGetter
from ..passes.transforms import SubstitutionPass, SubMapping, ConstFoldPass, ResolveBoundVars
from .spec import PuzzleSpec

class PuzzleSpecBuilder(PuzzleSpec):
    def __init__(self, name: str, desc: str, topo: Topology):
        self.name = name
        self.desc = desc
        self.topo = topo
        super().__init__(name, desc, topo, SymTable(), TypeEnv(), ShapeEnv(), ir.List())

        self._name_name_cnt = 0

        # Params are declared before intiializing Builder.
        # During the Builder lifetime, these are stored in _params
        # Register these used parameters from topo
        self._params = {}
        self._register_params(topo.terms_node())

    def _register_params(self, terms: ir.Node):
        pset = ParamGetter()(terms, ctx=Context()).vars
        for p in pset:
            assert isinstance(p, ir._Param)
            if p.name in self._params and p.T != self._params[p.name]:
                raise ValueError(f"param {p.name} already exists")
            self._params[p.name] = p.T

    def _new_var_name(self):
        self._var_name_cnt += 1
        return f"x{self._var_name_cnt}"

    def __repr__(self):
        return f"PuzzleSpecBuilder(name={self.name}, desc={self.desc}, topo={self.topo})"
    
    def _create_var(self, sort: irT.Type_, role: str, name: tp.Optional[str] = None) -> ast.Expr:
        if name is None:
            name = self._new_var_name()
        assert role in "GDP"
        sid = self.sym.new_var(name, role)
        v = ast.wrap(ir.VarRef(sid), sort)
        self.tenv.add(sid, sort)
        return sid, v

    def var(self, sort: irT.Type_, gen: bool=False, name: tp.Optional[str] = None) -> ast.Expr:
        role = "G" if gen else "D"
        sid, v = self._create_var(sort, role, name)
        self.shape_env.add(sid, sort)
        return v

    def var_list(self, size: ast.IntExpr, sort: irT.Type_, gen: bool=False, name: tp.Optional[str] = None) -> ast.ListExpr[irT.Type_]:
        role = "G" if gen else "D"
        varT = irT.ListT(sort)
        sid, v = self._create_var(varT, role, name)
        self.shape_env.add(sid, varT, shape=size.node)
        return v

    def var_dict(self, keys: ast.ListExpr[ast.Expr], sort: irT.Type_, name: str, gen: bool=False) -> ast.DictExpr[ast.Expr, irT.Type_]:
        role = "G" if gen else "D"
        varT = irT.DictT(keys.elem_type, sort)
        sid, v = self._create_var(varT, role, name)
        self.shape_env.add(sid, varT, shape=keys.node)
        return v

    def _replace_rules(self, new_rules: ir.Node):
        self._rules = new_rules
 
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
        # Extract all Parameters and add to sym table if they do not already exist
        self._register_params(self._rules)

        #  2: Resolve Placeholders (for bound bars/lambdas) and run CSE
        pm = PassManager(ResolveBoundVars(), CSE())
        self._replace_rules(pm.run(self._rules))
        self._type_check()
        return self

    def _unify_params(self):
        smap = SubMapping()
        for pname, T in self._params.items():
            sid, v = self._create_var(T, 'P', pname)
            self.shape_env.add(sid, T, shape=None)
            smap.add(
                match=lambda node, pname=pname: isinstance(node, ir._Param) and node.name==pname,
                replace=lambda node, sid=sid: ir.VarRef(sid)
            )
        ctx = Context()
        ctx.add(smap)
        new_topo, new_shape_env, new_rules, _ = self._transform([SubstitutionPass()], ctx=ctx)
        self.topo = new_topo
        self.shape_env = new_shape_env
        self._replace_rules(new_rules)

    # Freezes the spec and makes it immutable 
    def build(self) -> PuzzleSpec:
        # 1) Unify parameters (change parameters to vars)
        self._unify_params()
        all_vars = []
        for sid in self.sym:
            name = self.sym.get_name(sid)
            T = self.tenv[sid]
            role = self.sym.get_role(sid)
            shape = self.shape_env.get_shape(sid)
            all_vars.append((sid, name, T, role, shape))

        spec = PuzzleSpec.make(
            self.name,
            self.desc,
            self.topo,
            all_vars,
            self._rules
        )
        return spec.optimize()

        # TODO run passes on spec

        # Print AST
        # 3) Fold/invalidate the shape_env
        #   - eg, replace any Len(Var) with the shape_env size
        #   - eg, Replace any Keys(Var) with shape_env keys
        # 2) Run simplification loop
        # Do type checking/shape validation
        # Extract implicit constraints
        return spec
    
