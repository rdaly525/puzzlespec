from ast import Pass, Sub
import typing as tp

from puzzlespec.compiler.passes.transforms.substitution import SubMapping, SubstitutionPass
from puzzlespec.compiler.passes.canonicalize import _canonicalize
from . import ast, ir, ir_types as irT
from .topology import Topology, Grid2D

from .envs import SymTable, TypeEnv, ShapeEnv
from ..passes.pass_base import PassManager, Context
from ..passes.analyses.type_inference import TypeInferencePass, TypeEnv_, TypeValues
from ..passes.analyses.sym_table import SymTableEnv_


class PuzzleSpec:

    def __init__(self,
        name: str,
        desc: str,
        topo: Topology,
        sym: SymTable,
        tenv: TypeEnv,
        shape_env: ShapeEnv,
        rules: ir.List
    ):
        self.name = name
        self.desc = desc
        self.topo = topo
        self.sym = sym
        self.tenv = tenv
        self.shape_env = shape_env
        self._rules = _canonicalize(rules)
        self._type_check()

    @classmethod
    def make(cls,
        name: str,
        desc: str,
        topo: Topology,
        vars: tp.List[tp.Tuple[int, str, irT.Type_, str, ir.Node]] , # (cid, name, T, Role, shape)
        rules: tp.List[ir.Node]
    ):

        # Environments
        sym = SymTable()
        tenv = TypeEnv()
        shape_env = ShapeEnv()
        for (sid, name, T, role, shape) in vars:
            sym.add_var(sid=sid, name=name, role=role)
            tenv.add(sid=sid, sort=T)
            shape_env.add(sid=sid, T=T, shape=shape)

        return cls(name=name, desc=desc, topo=topo, sym=sym, tenv=tenv, shape_env=shape_env, rules=rules)

    def _type_check(self):
        if len(self._rules._children)==0:
            return
        pm = PassManager(TypeInferencePass())
        ctx = Context()
        ctx.add(TypeEnv_(self.tenv))
        pm.run(self._rules, ctx)
        tvals = ctx.get(TypeValues).mapping
        if tvals[self._rules] != irT.ListT(irT.Bool):
            for c in self._rules._children:
                if tvals[c] != irT.Bool:
                    raise ValueError(f"Constraint {c} is not bool, {tvals[c]}")

    # applies passes to the spec, returns the new topo, shape env, and rules
    def _transform(self, passes: tp.List[Pass], ctx: Context = None) -> tp.Tuple[Topology, ShapeEnv, ir.Node]:
        if ctx is None:
            ctx = Context()
        spec_node = _canonicalize(ir.Tuple(
            self.topo.terms_node(),
            self.shape_env.terms_node(),
            self._rules
        ))
        pm = PassManager(*passes)
        spec_node = pm.run(spec_node, ctx)
        topo_dim_node = spec_node._children[0]
        shape_env_node = spec_node._children[1]
        rules_node = spec_node._children[2]
        new_topo = Grid2D.make_from_terms_node(topo_dim_node)
        new_shape_env = self.shape_env.make_from_terms_node(shape_env_node)
        return new_topo, new_shape_env, rules_node

    # applies passes, copies the tenv and sym table, returns a new spec
    def transform(self, passes: tp.List[Pass], ctx: Context = None) -> 'PuzzleSpec':
        new_topo, new_shape_env, new_rules = self._transform(passes, ctx)
        new_tenv = self.tenv.copy()
        new_sym = self.sym.copy()
        return PuzzleSpec(name=self.name, desc=self.desc, topo=new_topo, sym=new_sym, tenv=new_tenv, shape_env=new_shape_env, rules=new_rules)

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
        return tp.cast(ast.BoolExpr, ast.wrap(self._rules, irT.ListT(irT.Bool)))

    # Returns a new spec with the params set
    def set_params(self, **kwargs) -> 'PuzzleSpec':
        # Run parameter substitution and constant propagation
        ctx = Context()
        param_sub_mapping = SubMapping()
        for pname, value in kwargs.items():
            if isinstance(value, int):
                new_node = ir.Lit(value, irT.Int)
            elif isinstance(value, bool):
                new_node = ir.Lit(value, irT.Bool)
            else:
                raise ValueError(f"Expected int or bool, got {type(value)}")

            sid = self.sym.get_sid(pname)
            role = self.sym.get_role(sid)
            if sid is None:
                raise ValueError(f"Param {pname} not found")
            if role != 'P':
                raise ValueError(f"Param {pname} with sid {sid} is not a parameter")

            param_sub_mapping.add(
                match=lambda node, sid=sid: isinstance(node, ir.VarRef) and node.sid==sid,
                replace=lambda node, new_node=new_node: new_node
            )
        ctx.add(
            param_sub_mapping
        )
        return self.transform([SubstitutionPass()], ctx)

    def pretty(self, constraint: ir.Node=None, dag=False) -> str:
        """Pretty print a constraint using the spec's type environment."""
        from ..passes.analyses.pretty_printer import PrettyPrinterPass, PrettyPrintedExpr
        from ..passes.analyses.type_inference import TypeInferencePass, TypeEnv_
        from ..passes.analyses.ssa_printer import SSAPrinter, SSAResult
        from ..passes.pass_base import Context, PassManager
        
        if constraint is None:
            constraint = self._rules

        ctx = Context()
        ctx.add(TypeEnv_(self.tenv))
        ctx.add(SymTableEnv_(self.sym))
        if dag:
            p = SSAPrinter()
        else:
            p = PrettyPrinterPass()
        pm = PassManager(
            TypeInferencePass(),
            p
        )
        # Run all passes and get the final result
        pm.run(constraint, ctx)
        
        # Get the pretty printed result from context
        if dag:
            text = ctx.get(SSAResult).text
        else:
            text = ctx.get(PrettyPrintedExpr).text

        return text