import typing as tp

from ..passes.analyses.ast_printer import AstPrinterPass
from ..passes.envobj import EnvsObj, OblsObj
from . import ir
from ..passes.analyses.pretty_printer import PrettyPrinterPass, PrettyPrintedExpr, pretty_spec
from .envs import SymTable
from ..passes.pass_base import PassManager, Context, Pass
from ..passes.transforms.beta_reduction import BetaReductionPass
from ..passes.transforms import CanonicalizePass, ConstFoldPass, AlgebraicSimplificationPass, DomainSimplificationPass
from ..passes.transforms.refine import RefineSimplify
from ..passes.transforms.cse import CSE
#from ..passes.analyses.constraint_categorizer import ConstraintCategorizer, ConstraintCategorizerVals
from ..passes.analyses.getter import VarGetter, VarSet, get_vars
from ..passes.analyses.kind_check import KindCheckingPass, TypeMap 
#from ..passes.analyses.ast_printer import AstPrinterPass, PrintedAST
from ..passes.pass_base import AnalysisObject, Analysis
class PuzzleSpec:

    def __init__(self,
        name: str,
        sym: SymTable,
        rules: ir.TupleLit=None,
        obls: ir.TupleLit=None
    ):
        self.name = name
        self.sym = sym
        if rules is None:
            rules = ir.TupleLit(ir.UnitT())
        else:
            assert isinstance(rules, ir.TupleLit)
        if obls is None:
            obls = ir.TupleLit(ir.TupleT())
        else:
            assert isinstance(obls, ir.TupleLit)
        self._spec = ir.Spec(cons=rules, obls=obls)
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
        return EnvsObj(sym=self.sym)

    @property
    def free_vars(self) -> tp.Set[ir.VarRef]:
        return get_vars(self._spec)

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

    # applies passes, copies the sym table, returns a new spec
    def transform(
        self,
        *passes: Pass,
        ctx: Context = None,
        verbose=True,
        analysis_map: tp.Mapping[tp.Type[AnalysisObject], Analysis] = {},
    ) -> 'PuzzleSpec':
        if ctx is None:
            ctx = Context()
        pm = PassManager(*passes, verbose=verbose, max_iter=10, analysis_map=analysis_map)
        new_spec_node = pm.run(self._spec, ctx=ctx)
        if new_spec_node == self._spec:
            return self
        pm = PassManager(VarGetter())
        pm.run(new_spec_node, ctx=ctx)
        new_sids = set(v.sid for v in ctx.get(VarSet).vars)
        new_sym = self.sym.copy(new_sids)
        obls = ctx.try_get(OblsObj)
        if obls is None:
            new_obls = new_spec_node.obls
        else:
            obls = obls.obls
            raw_obls = new_spec_node.obls._children[1:] + tuple(obls.values())
            new_obls = ir.TupleLit(ir.TupleT(*(ir.BoolT() for _ in raw_obls)), *raw_obls)
        return PuzzleSpec(
            name=self.name,
            sym=new_sym,
            rules=new_spec_node.cons,
            obls=new_obls,
        )

    def optimize(self) -> 'PuzzleSpec':
        ctx = Context(self.envs_obj)
        analysis_map = {
            TypeMap: KindCheckingPass()
        }

        opt_passes = [
            CanonicalizePass(),
            AlgebraicSimplificationPass(),
            ConstFoldPass(),
            DomainSimplificationPass(),
            RefineSimplify(),
            BetaReductionPass(),
            #CSE(),
        ]

        opt = self.transform(opt_passes, ctx=ctx, analysis_map=analysis_map)
        return opt
    
    def pretty(self) -> str:
        self._kind_check()
        return pretty_spec(self._spec, self.sym)

    def pretty_print(self):
        print(self.pretty())

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