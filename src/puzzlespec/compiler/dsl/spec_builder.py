import typing as tp

from puzzlespec.compiler.passes.analyses.ast_printer import AstPrinterPass, PrintedAST
from puzzlespec.compiler.passes.analyses.type_check import TypeCheckingPass
from puzzlespec.compiler.passes.analyses.pretty_printer import PrettyPrinterPass, pretty
from puzzlespec.compiler.passes.analyses.bound_var_check import CheckBoundVars
from puzzlespec.compiler.passes.transforms.resolve_vars import ResolveBoundVars, ResolveFreeVars, VarMap
from puzzlespec.compiler.passes.transforms.add_refinements import free_var_refine, add_refinements
from puzzlespec.compiler.passes.transforms.guard_opt import guard_opt
from . import ast, ir
from .envs import SymTable, TypeEnv
from ..passes.pass_base import Context, PassManager
from ..passes.transforms.cse import CSE
from ..passes.envobj import EnvsObj
from .spec import PuzzleSpec
from .utils import _substitute, _has_bv

class PuzzleSpecBuilder:
    def __init__(self):
        self.sym = SymTable()
        self._name_cnt = 0
        self._rules = []
        self.dom_cons = []

    def _add_rules(self, *new_rules: ast.Expr):
        self._rules += [r.node for r in new_rules]

    def __iadd__(self, other: tp.Union[ast.BoolExpr, tp.Iterable[ast.BoolExpr]]) -> tp.Self:
        
        constraints = other
        if not isinstance(other, tp.Iterable):
            constraints = [other]

        # Verify that all the constraints bool expressions    
        if not all(isinstance(c, ast.BoolExpr) for c in constraints):
            raise ValueError(f"Constraint, {constraints}, is not a BoolExpr")
        
        self._add_rules(*constraints)
        return self

    @property
    def constraints(self) -> ast.TupleExpr:
        return ast.TupleExpr.make(tuple(self._rules))

    # Freezes the spec and makes it immutable 
    def build(self, name: str, opt=True) -> PuzzleSpec:
        # 1: Resolve Placeholders (for bound bars/lambdas)
        ctx = Context()
        #pm = PassManager(TypeCheckingPass(), ResolveBoundVars(), verbose=True)
        pm = PassManager(TypeCheckingPass(), CheckBoundVars(), verbose=True)
        rules_node = ir.TupleLit(ir.TupleT(*(ir.BoolT() for _ in self._rules)), *self._rules)
        new_rules_node = pm.run(rules_node, ctx=ctx)

        # Refine free vars
        # Populate sym table and type environment
        sym = SymTable()
        ctx = Context(EnvsObj(sym))
        pm = PassManager(TypeCheckingPass(), ResolveFreeVars(), verbose=True)
        new_rules_node = pm.run(new_rules_node, ctx=ctx)
        #new_rules_node = guard_opt(new_rules_node)
        if isinstance(new_rules_node, ir.Guard):
            T, new_rules_node, p = new_rules_node._children
            obls = ast.TupleExpr.make((ast.wrap(p),)).node
        else:
            obls = ast.TupleExpr.make(()).node
        #new_rules_node = free_var_refine(new_rules_node)
        #new_rules_node = add_refinements(new_rules_node)
        env = ctx.get(EnvsObj)
        new_sym = env.sym
        spec = PuzzleSpec(
            name=name,
            sym=new_sym,
            rules=new_rules_node,
            obls=obls
        )
        # 3: Optimize/canonicalize
        if opt:
            spec = spec.optimize()
        return spec