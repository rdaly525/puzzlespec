from ast import Pass, Sub
from re import A
import typing as tp

from puzzlespec.compiler.passes.envobj import EnvsObj
#from puzzlespec.compiler.passes.analyses.ssa_printer import SSAPrinter
from puzzlespec.compiler.passes.transforms.substitution import SubMapping, SubstitutionPass
from . import ast, ir, ir_types as irT, proof_lib as pf

from .envs import SymTable, DomEnv
from ..passes.pass_base import PassManager, Context
from ..passes.transforms import CanonicalizePass, ConstFoldPass, AlgebraicSimplificationPass
from ..passes.analyses.constraint_categorizer import ConstraintCategorizer, ConstraintCategorizerVals
from ..passes.analyses.getter import VarGetter, VarSet
#from ..passes.analyses.ast_printer import AstPrinterPass, PrintedAST
from ..passes.analyses.evaluator import EvalPass, EvalResult, VarMap
from ..passes.analyses.inference import InferencePass, ProofResults
class PuzzleSpec:

    def __init__(self,
        name: str,
        sym: SymTable,
        domenv: DomEnv,
        rules: ir.TupleLit=None,
        obligations: ir.TupleLit=None,
    ):
        self.name = name
        self.sym = sym
        self.domenv = domenv
        if rules is None:
            rules = ir.TupleLit()
        if obligations is None:
            obligations = ir.TupleLit()
        self._spec_node = ir.TupleLit(rules, obligations)
        self._penv = self._inference()

    @property
    def envs_obj(self) -> EnvsObj:
        return EnvsObj(sym=self.sym, domenv=self.domenv, penv=self._penv)

    @property
    def rules_node(self) -> ir.TupleLit:
        return self._spec_node._children[0]

    @property
    def obls_node(self) -> ir.TupleLit:
        return self._spec_node._children[1]

    #@property
    #def domains_node(self) -> ir.TupleLit:
    #    doms = [self.domenv.get_doms(sid) for sid in self.domenv.entries.keys()]
    #    return ir.TupleLit(*doms)

    #def make_domenv(self, node: ir.Node) -> DomEnv:
    #    terms = node._children
    #    if len(terms) != len(self.domenv.entries):
    #        raise ValueError(f"Expected {len(self.domenv.entries)} terms, got {len(terms)}")
    #    domenv = DomEnv()
    #    for sid, doms_nodes in zip(self.domenv.entries.keys(), terms):
    #        domenv.add(sid, doms_nodes)
    #    return domenv

    def analyze(self, passes: tp.List[Pass], node: ir.Node=None, ctx: Context = None) -> Context:
        if ctx is None:
            ctx = Context()
        if node is None:
            node = self._spec_node
        pm = PassManager(*passes)
        pm.run(node, ctx)
        return ctx

    # Runs inference and returns new penv
    def _inference(self) -> tp.Dict[ir.Node, pf.ProofState]:
        ctx = Context(self.envs_obj)
        ctx = self.analyze([InferencePass()], self._spec_node, ctx)
        penv = ctx.get(ProofResults).penv
        rn, on = self.rules_node, self.obls_node
        rn_T, on_T = penv[rn].T, penv[on].T
        # rn and on must be tuple of bool
        for cn, cn_T in zip((rn, on), (rn_T, on_T)):
            if not (cn_T is irT.UnitType or isinstance(cn_T, irT.TupleT)):
                raise ValueError(f"{cn} must be a tuple, got {type(cn_T)}")
            for cn_c in cn._children:
                if penv[cn_c].T != irT.Bool:
                    raise ValueError(f"{cn_c} must be a bool, got {type(penv[cn_c].T)}")
        return penv

    # applies passes, copies the tenv and sym table, returns a new spec
    def transform(self, passes: tp.List[Pass], ctx: Context = None) -> 'PuzzleSpec':
        if ctx is None:
            ctx = Context()
        pm = PassManager(*passes, verbose=True)
        new_spec_node = pm.run(self._spec_node, ctx)
        if new_spec_node == self._spec_node:
            return self
        
        # Recompute penv
        penv = self._inference()

        new_sids = set(v.sid for v in ctx.get(VarSet).vars)
        new_sym = self.sym.copy(new_sids)
        new_domenv = self.make_domenv(dn)
        return PuzzleSpec(
            name=self.name,
            sym=new_sym,
            tenv=new_tenv,
            domenv=new_domenv,
            rules=rn,
            obligations=on
        )


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
        return tp.cast(ast.BoolExpr, ast.wrap(self._param_rules, irT.ListT(irT.Bool)))

    @property
    def gen_constraints(self) -> ast.BoolExpr:
        return tp.cast(ast.BoolExpr, ast.wrap(self._gen_rules, irT.ListT(irT.Bool)))

    @property
    def decision_constraints(self) -> ast.BoolExpr:
        return tp.cast(ast.BoolExpr, ast.wrap(self._decision_rules, irT.ListT(irT.Bool)))

    @property
    def constant_constraints(self) -> ast.BoolExpr:
        return tp.cast(ast.BoolExpr, ast.wrap(self._constant_rules, irT.ListT(irT.Bool)))

    def _categorize_constraints(self):
        pm = PassManager(ConstraintCategorizer())
        ctx = Context()
        ctx.add(SymTableEnv_(self.sym))
        pm.run(self._rules, ctx)
        ccmapping = tp.cast(ConstraintCategorizerVals, ctx.get(ConstraintCategorizerVals)).mapping
        param_rules = []
        gen_rules = []
        decision_rules = []
        constant_rules = []

        for rule in self._rules._children:
            assert rule in ccmapping
            match (ccmapping[rule]):
                case "D":
                    decision_rules.append(rule)
                case "G":
                    gen_rules.append(rule)
                case "P":
                    param_rules.append(rule)
                case "C":
                    constant_rules.append(rule)
        self._param_rules = ir.List(*param_rules)
        self._gen_rules = ir.List(*gen_rules)
        self._decision_rules = ir.List(*decision_rules)
        self._constant_rules = ir.List(*constant_rules)

    #@classmethod
    #def make(cls,
    #    name: str,
    #    desc: str,
    #    vars: tp.List[tp.Tuple[int, str, irT.Type_, str, ir.Node]] , # (cid, name, T, Role, shape)
    #    rules: tp.List[ir.Node]
    #):

    #    # Environments
    #    sym = SymTable()
    #    tenv = TypeEnv()
    #    shape_env = ShapeEnv()
    #    for (sid, name, T, role, shape) in vars:
    #        sym.add_var(sid=sid, name=name, role=role)
    #        tenv.add(sid=sid, sort=T)
    #        shape_env.add(sid=sid, shape=shape)

    #    return cls(name=name, desc=desc, topo=topo, sym=sym, tenv=tenv, shape_env=shape_env, rules=rules)


    # Returns a new spec with the params set
    def set_params(self, **kwargs) -> 'PuzzleSpec':
        # Run parameter substitution and constant propagation
        ctx = Context()
        param_sub_mapping = SubMapping()
        for pname, value in kwargs.items():
            sid = self.sym.get_sid(pname)
            if sid is None:
                raise ValueError(f"Param {pname} not found")
            if self.sym.get_role(sid) != 'P':
                raise ValueError(f"Param {pname} with sid {sid} is not a parameter")
            val = self.tenv[sid].cast_as(value)
            param_sub_mapping.add(
                match=lambda node, sid=sid: isinstance(node, ir.VarRef) and node.sid==sid,
                replace=lambda node, val=val: ir.Lit(val, self.tenv[sid])
            )
        ctx.add(
            param_sub_mapping
        )
        return self.transform([SubstitutionPass()], ctx).optimize()

    def optimize(self) -> 'PuzzleSpec':
        ctx = Context()
        ctx.add(SymTableEnv_(self.sym))
        ctx.add(TypeEnv_(self.tenv))
        return self.transform([[
            CanonicalizePass(),
            ConstFoldPass(),
            AlgebraicSimplificationPass(),
            #CollectionSimplificationPass(),
        ]], ctx)

    #def concretize_types(self, cellIdxT):
    #    ctx = Context()
    #    ctx.add(TypeEncoding(c_encoding=cellIdxT))
    #    new_topo, new_shape_env, new_rules, varset = self._transform([ConcretizeTypes()], ctx)
    #    sids = set(v.sid for v in varset.vars)
    #    new_tenv = TypeEnv()
    #    for sid in sids:
    #        oldT = self.tenv[sid]
    #        match oldT:
    #            case irT.CellIdxT:
    #                newT = cellIdxT
    #            case irT.DictT(irT.CellIdxT, valT):
    #                newT = irT.DictT(cellIdxT, valT)
    #            case _:
    #                newT = oldT
    #        new_tenv.add(sid, newT)
    #    new_sym = self.sym.copy(sids)
    #    return PuzzleSpec(
    #        name=self.name,
    #        desc=self.desc,
    #        topo=new_topo,
    #        sym=new_sym,
    #        tenv=new_tenv,
    #        shape_env=new_shape_env,
    #        rules=new_rules
    #    ).optimize()

    def clue_setter(self, cellIdxT: tp.Optional[irT.Type_]=None) -> 'Setter':
        if cellIdxT:
            spec = self.concretize_types(cellIdxT)
            print("After concretization:")
            print(spec.pretty(spec._spec_node))
        else:
            spec = self
        from .setter import Setter
        return Setter(spec)

    def evaluate(self, node: ir.Node, varmap: tp.Dict[int, tp.Any]=None) -> tp.Any:
        if varmap is None:
            varmap = {}
        ctx = self.analyze([EvalPass()], node, Context(VarMap(varmap)))
        return ctx.get(EvalResult).result

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