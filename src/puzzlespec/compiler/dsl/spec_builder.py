import typing as tp

from puzzlespec.compiler.passes.analyses.ast_printer import AstPrinterPass, PrintedAST
from puzzlespec.compiler.passes.transforms.resolve_vars import ResolveBoundVars, ResolveFreeVars, VarMap
from . import ast, ir
from .envs import SymTable, TypeEnv
from ..passes.pass_base import Context, PassManager
from ..passes.transforms.cse import CSE
from ..passes.envobj import EnvsObj
from .spec import PuzzleSpec

class PuzzleSpecBuilder:
    def __init__(self):
        self.sym = SymTable()
        self._name_cnt = 0
        self._rules = []

    def _new_var_name(self):
        self._var_name_cnt += 1
        return f"_X{self._var_name_cnt}"

    def var(self, 
        role: str, 
        sort: ir.Type,
        dom: tp.Optional[ast.DomainExpr]=None, 
        name: tp.Optional[str]=None, 
    ) -> ast.Expr:
        public = True
        if name is None:
            name = self._new_var_name()
            public = False
        sid = self.sym.new_var(name, role, public)
        var = ir._VarPlaceholder(sort, sid)
        return ast.wrap(var)

 
    # Core idea: Only allow vars with deps constructed via tabulate. In a tabulate, I can throw the domain/domT inside the bound var placeholder.
    # This now gives me the tabulated domains asociated with the bound var and therefore I can eagerly construct the nested Func var
    #def var(self, 
    #    role: str='D', 
    #    sort: tp.Optional[irT.Type_]=None, 
    #    dom: tp.Optional[ast.DomainExpr]=None, 
    #    name: tp.Optional[str]=None, 
    #    dep: tp.Optional[tp.Tuple[ast.Expr, ...]]=None
    #) -> ast.Expr:
    #    err_prefix=f"ERROR In var {name}: "
    #    if dom is not None and not isinstance(dom, ast.DomainExpr):
    #        raise ValueError(f"{err_prefix}dom must be a DomainExpr, got {type(dom)}")
    #    if sort is not None and not isinstance(sort, irT.Type_):
    #        raise ValueError(f"{err_prefix}sort must be a Type_, got {type(sort)}")
    #    if role not in "GDP":
    #        raise ValueError(f"{err_prefix}role must be G, P, or D, got {role}")
    #    if sort is None and dom is None:
    #        raise ValueError(f"{err_prefix}Either dom or sort must be provided")
    #    if dom is not None and sort is not None and dom.carT:
    #        raise ValueError(f"{err_prefix}dom.carT must be equal to sort, got {dom.carT} and {sort}")
    #    if dom is None:
    #        dom_expr = ast.wrap(ir.Universe(sort))
    #    else:
    #        dom_expr = dom
    #    if not isinstance(dep, tp.Tuple):
    #        dep = (dep,)
    #    if not all(isinstance(d.node, ir._BoundVarPlaceholder) for d in dep):
    #        raise ValueError(f"{err_prefix}dep must be bound variables, got {dep}")
    #    if not all(d.node.is_tabulate for d in dep):
    #        raise ValueError(f"{err_prefix}dep must be tabulated bound variables, got {dep}")
    #    dep_doms = []
    #    for bv in dep:
    #        wit = bv.penv[bv.node].get_wit(pf.DomsWit)
    #        assert len(wit.doms) ==1
    #        dep_dom = wit.doms[0]
    #        dep_doms.append(ast.wrap(dep_dom, bv.penv))

    #    #dep_dom_nodes = tuple(d.node.dom for d in dep)
    #  
    #    ## Do dependency analysis
    #    #dep_sid_sets= tuple(set(v.sid for v in self.analyze([VarGetter()], d.node, Context(self._envs_obj)).get(VarSet).vars) for d in dep)
    #    #sids_in_context = set()
    #    #for i, dep_set in enumerate(dep_sid_sets):
    #    #    for sid in dep_set:
    #    #        for dep_sid in self._depends[sid]:
    #    #            if dep_sid not in sids_in_context:
    #    #                msg =f"{err_prefix}Variable Dependency Error!\n . bound_var in Dom:{dep[i]} is dependent on {self.sym.get_name(dep_sid)} which is not in context."
    #    #                raise ValueError(msg)
    #    #    sids_in_context |= dep_set
    #    
    #    public = True
    #    if name is None:
    #        name = self._new_var_name()
    #        public = False
    #    
    #    new_sid = self.sym.new_var(name, role, public)

    #    #self._depends[new_sid] = sids_in_context
    #    doms = (*dep_doms, dom_expr)
    #    doms_nodes = tuple(dom.node for dom in doms)
    #    # update domain env
    #    self.domenv.add(new_sid, doms_nodes)
    #   
    #    #Calculate expr of var
    #    var_node = ir.VarRef(new_sid)
    #    penv = ast._mix_envs(*doms)
    #    def _T(doms):
    #        if len(doms)==1:
    #            return doms[0].T.carT
    #        else:
    #            return irT.FuncT(domT=doms[0].T, resT=_T(doms[1:]))
    #    varT = _T(doms)
    #    penv[var_node] = pf.ProofState(
    #        pf.DomsWit(doms=doms_nodes, subject=var_node),
    #        pf.TypeWit(T=varT, subject=var_node)
    #    )
    #    var = ast.wrap(var_node, penv)
    #    for d in dep:
    #        var = var.apply(d)
    #    return var

    def param(self, sort: ir.Type=None, name: str=None) -> ast.Expr:
        return self.var(role='P', sort=sort, name=name)
    
    def gen_var(self, sort: ir.Type=None, name: str=None) -> ast.Expr:
        return self.var(role='G', sort=sort, name=name)
    
    def decision_var(self, sort: ir.Type=None, name: str=None) -> ast.Expr:
        return self.var(role='D', sort=sort, name=name)


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

    # Freezes the spec and makes it immutable 
    def build(self, name: str) -> PuzzleSpec:
        #self.print()
        # 1: Resolve Placeholders (for bound bars/lambdas)
        pm = PassManager(ResolveBoundVars(), verbose=True)
        rules_node = ir.TupleLit(ir.TupleT(*(ir.BoolT() for _ in self._rules)), *self._rules)
        new_rules_node = pm.run(rules_node)
        # Populate tenv
        ctx = Context()
        pm = PassManager([])
        pm = PassManager(ResolveFreeVars(), CSE(), verbose=True)
        new_rules_node = pm.run(new_rules_node, ctx)
        sid_to_T = ctx.get(VarMap).sid_to_T
        assert len(sid_to_T) != 0
        tenv = TypeEnv()
        for sid, T in sid_to_T.items():
            tenv.add(sid, T)
        spec = PuzzleSpec(
            name=name,
            sym=self.sym.copy(),
            tenv=tenv,
            rules=new_rules_node
        )
        # 3: Optimize/canonicalize
        spec_opt = spec.optimize()
        spec_opt.pretty()
        assert 0
        return spec_opt

    def print(self, rules_node=None):
        if rules_node is None:
            rules_node = ir.TupleLit(ir.TupleT(*(ir.BoolT() for _ in self._rules)), *self._rules)
        ctx = Context()
        pm = PassManager([AstPrinterPass()], verbose=True)
        pm.run(rules_node, ctx)
        a = ctx.get(PrintedAST)
        print(a.text)