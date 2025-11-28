import typing as tp

from puzzlespec.compiler.passes.analyses.ast_printer import AstPrinterPass
from puzzlespec.compiler.passes.envobj import EnvsObj
from puzzlespec.compiler.passes.transforms.substitution import SubMapping, SubstitutionPass
from . import ir
from ..passes.analyses.pretty_printer import PrettyPrinterPass, PrettyPrintedExpr
from .envs import SymTable, TypeEnv
from ..passes.pass_base import PassManager, Context, Pass
from puzzlespec.compiler.passes.transforms.beta_reduction import BetaReductionPass
from ..passes.transforms import CanonicalizePass, ConstFoldPass, AlgebraicSimplificationPass, DomainSimplificationPass
from ..passes.transforms.cse import CSE
#from ..passes.analyses.constraint_categorizer import ConstraintCategorizer, ConstraintCategorizerVals
from ..passes.analyses.getter import VarGetter, VarSet
from ..passes.analyses.kind_check import KindCheckingPass
#from ..passes.analyses.ast_printer import AstPrinterPass, PrintedAST
from ..passes.analyses.evaluator import EvalPass, EvalResult, VarMap
from .utils import _is_kind
class PuzzleSpec:

    def __init__(self,
        name: str,
        sym: SymTable,
        tenv: TypeEnv,
        rules: ir.TupleLit=None,
        num_rules: int = None
    ):
        self.name = name
        self.sym = sym
        self.tenv = tenv
        if rules is None:
            rules = ir.TupleLit()
        if num_rules is None:
            num_rules = rules.num_children
        if num_rules > rules.num_children:
            raise ValueError(f"Expected at most {rules.num_children} rules, got {num_rules}")
        self._rules = rules
        self._num_rules = num_rules
        self._ph_check()
        self._kind_check()

    def _ph_check(self):
        def check(node: ir.Node):
            if isinstance(node, (ir._BoundVarPlaceholder, ir._LambdaPlaceholder, ir._LambdaTPlaceholder, ir._VarPlaceholder)):
                raise ValueError(f"Found placeholder node {node} in rules")
            for c in node._children:
                check(c)
        check(self._rules)

    @property
    def rules_T(self) -> ir.Type:
        return ir.TupleT(*(ir.BoolT() for _ in self._rules._children[1:]))

    @property
    def envs_obj(self) -> EnvsObj:
        return EnvsObj(sym=self.sym, tenv=self.tenv)

    def analyze(self, passes: tp.List[Pass], node: ir.Node=None, ctx: Context = None) -> Context:
        if ctx is None:
            ctx = Context()
        if node is None:
            node = self._rules
        pm = PassManager(*passes)
        pm.run(node, ctx)
        return ctx

    def _kind_check(self):
        ctx = Context(self.envs_obj)
        self.analyze([KindCheckingPass()], ctx=ctx)
        # Check that the rules are a TupleT of BoolT
        if not _is_kind(self._rules.T, ir.TupleT):
            raise TypeError(f"Expected rules to have type {ir.TupleT(*(ir.BoolT() for _ in self._rules))}, got {self._rules.T}")
        for rule in self._rules._children[1:]:
            if not _is_kind(rule.T, ir.BoolT):
                raise TypeError(f"Expected rule to have type BoolT, got {rule.T}")

    # applies passes, copies the tenv and sym table, returns a new spec
    def transform(self, *passes: Pass, ctx: Context = None, verbose=True) -> 'PuzzleSpec':
        if ctx is None:
            ctx = Context()
        pm = PassManager(*passes, verbose=verbose, max_iter=10)
        new_spec_node = pm.run(self._rules, ctx=ctx)
        if new_spec_node == self._rules:
            return self
        pm = PassManager(VarGetter())
        pm.run(new_spec_node, ctx=ctx)
        new_sids = set(v.sid for v in ctx.get(VarSet).vars)
        new_sym = self.sym.copy(new_sids)
        new_tenv = self.tenv.copy()
        return PuzzleSpec(
            name=self.name,
            sym=new_sym,
            tenv=new_tenv,
            rules=new_spec_node
        )

    def optimize(self) -> 'PuzzleSpec':
        ctx = Context()
        opt_passes = [
            CanonicalizePass(),
            AlgebraicSimplificationPass(),
            ConstFoldPass(),
            DomainSimplificationPass(),
            BetaReductionPass(),
            #CSE(),
        ]
        #spec = self
        #for op in opt_passes:
        #    spec.pretty()
        #    spec.transform(op, ctx=ctx)

        opt = self.transform(opt_passes, ctx=ctx)
        #print("NOBETA")
        #opt.pretty()
        #opt = opt.transform(BetaReductionPass(), ctx=ctx)
        #print("BETA")
        #opt.pretty()
        return opt
    
    def pretty(self, dag=False) -> str:
        if dag:
            raise NotImplementedError()
        ctx = Context(self.envs_obj)
        pm = PassManager(
            #AstPrinterPass(),
            KindCheckingPass(),
            PrettyPrinterPass(),
            verbose=True
        )
        pm.run(self._rules, ctx)
        return ctx.get(PrettyPrintedExpr).text



    #@property
    #def rules_node(self) -> ir.TupleLit:
    #    return self._spec_node._children[0]

    #@property
    #def obls_node(self) -> ir.TupleLit:
    #    return self._spec_node._children[1]

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

    # Runs inference and returns new penv
    #def _inference(self, root: ir.Node=None) -> tp.Dict[ir.Node, pf.ProofState]:
    #    ctx = Context(self.envs_obj)
    #    ctx = self.analyze([InferencePass()], self._spec_node, ctx)
    #    penv = ctx.get(ProofResults).penv
    #    rn, on = self.rules_node, self.obls_node
    #    rn_T, on_T = penv[rn].T, penv[on].T
    #    # rn and on must be tuple of bool
    #    for cn, cn_T in zip((rn, on), (rn_T, on_T)):
    #        if not (cn_T is irT.UnitType or isinstance(cn_T, irT.TupleT)):
    #            raise ValueError(f"{cn} must be a tuple, got {type(cn_T)}")
    #        for cn_c in cn._children:
    #            if penv[cn_c].T != irT.Bool:
    #                raise ValueError(f"{cn_c} must be a bool, got {type(penv[cn_c].T)}")
    #    return penv



    # TODO
    #def __repr__(self):
    #    return f"PuzzleSpec(name={self.name}, desc={self.desc}, topo={self.topo})"
    
    ## Returns a dict of param names to param node
    #@property
    #def params(self) -> tp.Dict[str, ast.Expr]:
    #    return {self.sym.get_name(sid): ast.wrap(ir.VarRef(sid), self.tenv[sid]) for sid in self.sym.get_params()}

    ## Returns a dict of gen var names to gen var node
    #@property
    #def gen_vars(self) -> tp.Dict[str, ast.Expr]:
    #    return {self.sym.get_name(sid): ast.wrap(ir.VarRef(sid), self.tenv[sid]) for sid in self.sym.get_gen_vars()}

    ## Returns a dict of decision var names to decision var node
    #@property
    #def decision_vars(self) -> tp.Dict[str, ast.Expr]:
    #    return {self.sym.get_name(sid): ast.wrap(ir.VarRef(sid), self.tenv[sid]) for sid in self.sym.get_decision_vars()}

    #@property
    #def param_constraints(self) -> ast.BoolExpr:
    #    return tp.cast(ast.BoolExpr, ast.wrap(self._param_rules, irT.ListT(irT.Bool)))

    #@property
    #def gen_constraints(self) -> ast.BoolExpr:
    #    return tp.cast(ast.BoolExpr, ast.wrap(self._gen_rules, irT.ListT(irT.Bool)))

    #@property
    #def decision_constraints(self) -> ast.BoolExpr:
    #    return tp.cast(ast.BoolExpr, ast.wrap(self._decision_rules, irT.ListT(irT.Bool)))

    #@property
    #def constant_constraints(self) -> ast.BoolExpr:
    #    return tp.cast(ast.BoolExpr, ast.wrap(self._constant_rules, irT.ListT(irT.Bool)))

    #def _categorize_constraints(self):
    #    pm = PassManager(ConstraintCategorizer())
    #    ctx = Context()
    #    ctx.add(SymTableEnv_(self.sym))
    #    pm.run(self._rules, ctx)
    #    ccmapping = tp.cast(ConstraintCategorizerVals, ctx.get(ConstraintCategorizerVals)).mapping
    #    param_rules = []
    #    gen_rules = []
    #    decision_rules = []
    #    constant_rules = []

    #    for rule in self._rules._children:
    #        assert rule in ccmapping
    #        match (ccmapping[rule]):
    #            case "D":
    #                decision_rules.append(rule)
    #            case "G":
    #                gen_rules.append(rule)
    #            case "P":
    #                param_rules.append(rule)
    #            case "C":
    #                constant_rules.append(rule)
    #    self._param_rules = ir.List(*param_rules)
    #    self._gen_rules = ir.List(*gen_rules)
    #    self._decision_rules = ir.List(*decision_rules)
    #    self._constant_rules = ir.List(*constant_rules)


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

    #def clue_setter(self, cellIdxT: tp.Optional[ir.Type]=None) -> 'Setter':
    #    if cellIdxT:
    #        spec = self.concretize_types(cellIdxT)
    #        print("After concretization:")
    #        print(spec.pretty(spec._spec_node))
    #    else:
    #        spec = self
    #    from .setter import Setter
    #    return Setter(spec)

    #def evaluate(self, node: ir.Node, varmap: tp.Dict[int, tp.Any]=None) -> tp.Any:
    #    if varmap is None:
    #        varmap = {}
    #    ctx = self.analyze([EvalPass()], node, Context(VarMap(varmap)))
    #    return ctx.get(EvalResult).result

    #def pretty(self, constraint: ir.Node=None, dag=False) -> str:
    #    """Pretty print a constraint using the spec's type environment."""
    #    from ..passes.analyses.pretty_printer import PrettyPrinterPass, PrettyPrintedExpr
    #    from ..passes.analyses.type_inference import TypeInferencePass, TypeEnv_
    #    from ..passes.analyses.ssa_printer import SSAPrinter, SSAResult
    #    from ..passes.pass_base import Context, PassManager
    #    
    #    if constraint is None:
    #        constraint = self._rules

    #    ctx = Context()
    #    ctx.add(TypeEnv_(self.tenv))
    #    ctx.add(SymTableEnv_(self.sym))
    #    if dag:
    #        p = SSAPrinter()
    #    else:
    #        p = PrettyPrinterPass()
    #    pm = PassManager(
    #        TypeInferencePass(),
    #        p
    #    )
    #    # Run all passes and get the final result
    #    pm.run(constraint, ctx)
    #    
    #    # Get the pretty printed result from context
    #    if dag:
    #        text = ctx.get(SSAResult).text
    #    else:
    #        text = ctx.get(PrettyPrintedExpr).text

    #    return text