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
        obls: ir.TupleLit=None
    ):
        self.name = name
        self.sym = sym
        self.tenv = tenv
        if rules is None:
            rules = ir.TupleLit(ir.UnitT())
        else:
            assert isinstance(rules, ir.TupleLit)
        if obls is None:
            obls = ir.TupleLit(ir.TupleT())
        else:
            assert isinstance(obls, ir.TupleLit)
        Ts = ir.TupleT(*self.tenv.vars.values())
        self._spec = ir.Spec(cons=rules, obls=obls, Ts=Ts)
        self._ph_check()
        self._kind_check()

    def _ph_check(self):
        def check(node: ir.Node):
            if isinstance(node, (ir.BoundVarHOAS, ir.LambdaHOAS, ir.PiTHOAS, ir.VarHOAS)):
                raise ValueError(f"Found placeholder node {node} in rules")
            for c in node._children:
                check(c)
        check(self._spec)

    @property
    def envs_obj(self) -> EnvsObj:
        return EnvsObj(sym=self.sym, tenv=self.tenv)

    def analyze(self, passes: tp.List[Pass], node: ir.Node=None, ctx: Context = None) -> Context:
        if ctx is None:
            ctx = Context()
        if node is None:
            node = self._spec
        pm = PassManager(*passes)
        pm.run(node, ctx)
        return ctx

    def _kind_check(self):
        ctx = Context(self.envs_obj)
        self.analyze([KindCheckingPass()], ctx=ctx)

    # applies passes, copies the tenv and sym table, returns a new spec
    def transform(self, *passes: Pass, ctx: Context = None, verbose=True) -> 'PuzzleSpec':
        if ctx is None:
            ctx = Context()
        pm = PassManager(*passes, verbose=verbose, max_iter=10)
        new_spec_node = pm.run(self._spec, ctx=ctx)
        if new_spec_node == self._spec:
            return self
        pm = PassManager(VarGetter())
        pm.run(new_spec_node, ctx=ctx)
        new_sids = set(v.sid for v in ctx.get(VarSet).vars)
        new_sym = self.sym.copy(new_sids)
        new_tenv = self.tenv.copy(new_spec_node.Ts._children)
        return PuzzleSpec(
            name=self.name,
            sym=new_sym,
            tenv=new_tenv,
            rules=new_spec_node.cons,
            obls=new_spec_node.obls,
        )

    def optimize(self, max_dom_size=20) -> 'PuzzleSpec':
        ctx = Context()
        opt_passes = [
            CanonicalizePass(),
            AlgebraicSimplificationPass(),
            ConstFoldPass(max_dom_size=max_dom_size),
            DomainSimplificationPass(),
            BetaReductionPass(),
            #CSE(),
        ]

        opt = self.transform(opt_passes, ctx=ctx)
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
        pm.run(self._spec, ctx)
        return ctx.get(PrettyPrintedExpr).text

    # Returns a dict of param names to sid
    @property
    def params(self) -> tp.Dict[str, int]:
        return {self.sym.get_name(sid):sid for sid in self.sym.get_params()}

    # Returns a dict of gen var names to sid
    @property
    def gen_vars(self) -> tp.Dict[str, int]:
        return {self.sym.get_name(sid): sid for sid in self.sym.get_gen_vars()}

    # Returns a dict of decision var names to sid
    @property
    def decision_vars(self) -> tp.Dict[str, int]:
        return {self.sym.get_name(sid): sid for sid in self.sym.get_decision_vars()}

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
    #def set_params(self, **kwargs) -> 'PuzzleSpec':
    #    # Run parameter substitution and constant propagation
    #    ctx = Context()
    #    param_sub_mapping = SubMapping()
    #    for pname, value in kwargs.items():
    #        sid = self.sym.get_sid(pname)
    #        if sid is None:
    #            raise ValueError(f"Param {pname} not found")
    #        if self.sym.get_role(sid) != 'P':
    #            raise ValueError(f"Param {pname} with sid {sid} is not a parameter")
    #        val = self.tenv[sid].cast_as(value)
    #        param_sub_mapping.add(
    #            match=lambda node, sid=sid: isinstance(node, ir.VarRef) and node.sid==sid,
    #            replace=lambda node, val=val: ir.Lit(val, self.tenv[sid])
    #        )
    #    ctx.add(
    #        param_sub_mapping
    #    )
    #    return self.transform([SubstitutionPass()], ctx).optimize()

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