import typing as tp

from puzzlespec.compiler.passes.analyses.ast_printer import AstPrinterPass, PrintedAST
from puzzlespec.compiler.passes.analyses.kind_check import KindCheckingPass
from puzzlespec.compiler.passes.analyses.pretty_printer import PrettyPrinterPass, pretty
from puzzlespec.compiler.passes.transforms.resolve_vars import ResolveBoundVars, ResolveFreeVars, VarMap
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

    def _new_var_name(self):
        self._var_name_cnt += 1
        return f"_X{self._var_name_cnt}"

    #def func_var(self, 
    #    role: str, 
    #    dom: tp.Optional[ast.DomainExpr],
    #    sort: ir.Type=None,
    #    codom: tp.Optional[ast.DomainExpr]=None,
    #    name: tp.Optional[str]=None, 
    #):
    #    #if sort is not None:
    #    #    assert codom is None
    #    #if codom is not None:
    #    #    assert sort is None
    #    #    sort = codom.carT
    #    #new_bv = ir.BoundVarHOAS(dom.carT)
    #    #T = ir.FuncT(
    #    #    dom.node,
    #    #    ir.PiTHOAS(
    #    #        new_bv,
    #    #        sort
    #    #    )
    #    #)
    #    #var = self.var(role, T, None, name, None)
    #    #self += var.forall(lambda v: codom.contains(v))
    #    #return var
    #    return dom.map(lambda i: self.var(
    #        role=role,
    #        sort=sort,
    #        dom=codom,
    #        name=name,
    #        indices=(i,)
    #    ))

    #def var(self, 
    #    role: str='D', 
    #    sort: ast.TExpr=None,
    #    dom: tp.Optional[ast.DomainExpr]=None,
    #    name: tp.Optional[str]=None, 
    #    indices: tp.Optional[tp.Tuple[ast.Expr, ...]]=None
    #) -> ast.Expr:
    #    metadata = dict(role=role)

    #    #public = True
    #    #if name is None:
    #    #    name = self._new_var_name()
    #    #    public = False
    #    err_prefix=f"ERROR In var {name}: "
    #    if sort is not None and not isinstance(sort, ast.TExpr):
    #        raise ValueError(f"{err_prefix}sort must be a TExpr, got {type(sort)}")
    #    if role not in "GDP":
    #        raise ValueError(f"{err_prefix}role must be G, P, or D, got {role}")
    #    if sum((sort is None, dom is None)) != 1:
    #        raise ValueError(f"{err_prefix}Either codom or sort must be provided")
    #    if indices is None:
    #        bv_exprs = ()
    #    elif not isinstance(indices, tp.Tuple):
    #        bv_exprs = (indices,)
    #    else:
    #        bv_exprs = indices
    #    bvs = [e.node for e in bv_exprs]
    #    if not all(isinstance(bv, ir.BoundVarHOAS) for bv in bvs):
    #        raise ValueError(f"{err_prefix}indices must be bound variables, got {indices}")
    #    if not all(hasattr(e, '_map_dom') for e in bv_exprs):
    #        raise ValueError(f"{err_prefix}indices must be 'mapped' bound variables, got {indices}")
    #    if sort is None:
    #        sort = dom.T.carT

    #    ## Do dependency analysis
    #    # indices = (i,j,k)
    #    # dom(i) and i must not depend on (i,j,k)
    #    # dom(j) and j must not depend on (j,k)
    #    # ...
    #    for i, cur_bv in enumerate(bv_exprs):
    #        for j, bv in enumerate(bv_exprs[i:]):
    #            if _has_bv(bv.node, cur_bv.T.node):
    #                raise ValueError(f"indices[{i}].T depends on indices[{i+j}]")
    #            if _has_bv(bv.node, cur_bv._map_dom.node):
    #                raise ValueError(f"Dom[indices[{i}]] depends on indices[{i+j}]")
    #   
    #    #public = True
    #    #if name is None:
    #    #    name = self._new_var_name()
    #    #    public = False
    #    #sid = self.sym.new_var(name, role, public)
    #    def _any_bv(n: ir.Node):
    #        if isinstance(n, ir.BoundVarHOAS):
    #            return True
    #        return any(_any_bv(c) for c in n._children)
    #    if dom is not None and _any_bv(dom.node):
    #        raise NotImplementedError("cannot handle dependent doms")
    #    
    #    # This is very brittle code
    #    # High level: for indices=(i,j) dom(j) might depend on i. so I need to substitute the new boundvar of i into dom(j)
    #    bv_map = {}
    #    def make_sort(bves: tp.Tuple[ast.Expr]) -> ir.Type:
    #        if len(bves)==0:
    #            return sort.node
    #        old_bv = bves[0].node
    #        bv_T = bves[0]._T.node
    #        bv_dom: ast.DomainExpr = bves[0]._map_dom.node
    #        for o, n in bv_map.items():
    #            bv_dom = _substitute(bv_dom, o, n)
    #            bv_T = _substitute(bv_T, o, n)
    #        new_bv = ir.BoundVarHOAS(bv_T)
    #        for o, n in bv_map.items():
    #            bv_dom = _substitute(bv_dom, o, n)
    #        bv_map[old_bv] = new_bv
    #        T = ir.FuncT(
    #            bv_dom,
    #            ir.PiTHOAS(
    #                new_bv,
    #                make_sort(bves[1:])
    #            )
    #        )
    #        return T
    #    full_sort = make_sort(bv_exprs)
    #    var = ir.VarHOAS(full_sort, name=name, metadata=metadata)
    #    var = ast.wrap(var)
    #    # add dom constraint

    #    if dom is not None:
    #        def _con(val):
    #            if isinstance(val.T, ast.FuncType):
    #                return val.forall(lambda v: _con(v))
    #            return dom.contains(val)
    #        self += _con(var)
    #    for e in bv_exprs:
    #        var = var(e)
    #    return var

    #def param(self, sort: ir.Type=None, name: str=None) -> ast.Expr:
    #    return self.var(role='P', sort=sort, name=name)
    
    #def gen_var(self, sort: ir.Type=None, name: str=None) -> ast.Expr:
    #    return self.var(role='G', sort=sort, name=name)
    
    #def decision_var(self, sort: ir.Type=None, name: str=None) -> ast.Expr:
    #    return self.var(role='D', sort=sort, name=name)


    #def param(self, sort: ir.Type=None, dom: ast.DomainExpr=None, name: str=None, dep=()) -> ast.Expr:
    #    return self.var(sort=sort, dom=dom, name=name, dep=dep)
    
    #def gen_var(self, sort: ir.Type=None, dom: ast.DomainExpr=None, name: str=None, dep=()) -> ast.Expr:
    #    return self.var(sort=sort, dom=dom, name=name, dep=dep)
    
    #def decision_var(self, sort: ir.Type=None, dom: ast.DomainExpr=None, name: str=None, dep=()) -> ast.Expr:
    #    return self.var(sort=sort, dom=dom, name=name, dep=dep)

    #def func_var(self, dom: ast.DomainExpr, role: str='G', sort: irT.Type_=None, codom: ast.DomainExpr=None, name: str=None) -> ast.Expr:
    #    return dom.map(lambda i: self.var(role, sort, codom, name, dep=i))

    #def _replace_rules(self, new_rules: tp.Iterable[ir.Node]):
    #    self._rules = ir.TupleLit(*new_rules)
 
    def _add_rules(self, *new_rules: ast.Expr):
        print("Adding rules:")
        for r in new_rules:
            print(pretty(r.node))
        self._rules += [r.node for r in new_rules]

    def __iadd__(self, other: tp.Union[ast.BoolExpr, tp.Iterable[ast.BoolExpr]]) -> tp.Self:
        
        constraints = other
        if not isinstance(other, tp.Iterable):
            constraints = [other]

        # Verify that all the constraints bool expressions    
        if not all(isinstance(c, ast.BoolExpr) for c in constraints):
            raise ValueError(f"Constraints, {constraints}, is not a BoolExpr")
        
        self._add_rules(*constraints)
        return self

    @property
    def constraints(self) -> ast.TupleExpr:
        return ast.TupleExpr.make(tuple(self._rules))

    # Freezes the spec and makes it immutable 
    def build(self, name: str) -> PuzzleSpec:
        # 1: Resolve Placeholders (for bound bars/lambdas)
        ctx = Context(EnvsObj(None, None))
        pm = PassManager(KindCheckingPass(), ResolveBoundVars(), verbose=True)
        rules_node = ir.TupleLit(ir.TupleT(*(ir.BoolT() for _ in self._rules)), *self._rules)
        new_rules_node = pm.run(rules_node, ctx=ctx)
        print(pretty(new_rules_node))

        # Populate sym table and type environment
        sym = SymTable()
        tenv = TypeEnv()
        ctx = Context(EnvsObj(sym, tenv))
        #pm = PassManager(KindCheckingPass(), AstPrinterPass(), ResolveFreeVars(), AstPrinterPass(), verbose=True)
        pm = PassManager(KindCheckingPass(), ResolveFreeVars(), verbose=True)
        new_rules_node = pm.run(new_rules_node, ctx=ctx)
        env = ctx.get(EnvsObj)
        new_sym = env.sym
        new_tenv = env.tenv

        spec = PuzzleSpec(
            name=name,
            sym=new_sym,
            tenv=new_tenv,
            rules=new_rules_node
        )
        #spec_obls = spec.extract_obligations()
        # 3: Optimize/canonicalize
        spec_opt = spec.optimize()
        return spec_opt

    #def print(self, rules_node=None):
    #    if rules_node is None:
    #        rules_node = ir.TupleLit(ir.TupleT(*(ir.BoolT() for _ in self._rules)), *self._rules)
    #    ctx = Context()
    #    pm = PassManager([AstPrinterPass()], verbose=True)
    #    pm.run(rules_node, ctx)
    #    a = ctx.get(PrintedAST)
    #    print(a.text)