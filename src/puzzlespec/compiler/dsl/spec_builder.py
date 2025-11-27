import typing as tp

from puzzlespec.compiler.passes.analyses.ast_printer import AstPrinterPass, PrintedAST
from puzzlespec.compiler.passes.analyses.kind_check import KindCheckingPass
from puzzlespec.compiler.passes.analyses.pretty_printer import PrettyPrinterPass
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

    def func_var(self, 
        role: str, 
        dom: tp.Optional[ast.DomainExpr],
        sort: ir.Type=None,
        codom: tp.Optional[ast.DomainExpr]=None,
        name: tp.Optional[str]=None, 
    ):
        #if sort is not None:
        #    assert codom is None
        #if codom is not None:
        #    assert sort is None
        #    sort = codom.carT
        #new_bv = ir._BoundVarPlaceholder(dom.carT)
        #T = ir.PiT(
        #    dom.node,
        #    ir._LambdaTPlaceholder(
        #        new_bv,
        #        sort
        #    )
        #)
        #var = self.var(role, T, None, name, None)
        #self += var.forall(lambda v: codom.contains(v))
        #return var
        return dom.map(lambda i: self.var(
            role=role,
            sort=sort,
            dom=codom,
            name=name,
            dep=(i,)
        ))

    def var(self, 
        role: str, 
        sort: ir.Type=None,
        dom: tp.Optional[ast.DomainExpr]=None,
        name: tp.Optional[str]=None, 
        dep: tp.Optional[tp.Tuple[ast.Expr, ...]]=None
    ) -> ast.Expr:
        public = True
        if name is None:
            name = self._new_var_name()
            public = False
        err_prefix=f"ERROR In var {name}: "
        if sort is not None and not isinstance(sort, ir.Type):
            raise ValueError(f"{err_prefix}sort must be a Type_, got {type(sort)}")
        if role not in "GDP":
            raise ValueError(f"{err_prefix}role must be G, P, or D, got {role}")
        if sum((sort is None, dom is None)) != 1:
            raise ValueError(f"{err_prefix}Either codom or sort must be provided")
        if dep is None:
            bv_exprs = ()
        elif not isinstance(dep, tp.Tuple):
            bv_exprs = (dep,)
        else:
            bv_exprs = dep
        bvs = [e.node for e in bv_exprs]
        if not all(isinstance(bv, ir._BoundVarPlaceholder) for bv in bvs):
            raise ValueError(f"{err_prefix}dep must be bound variables, got {dep}")
        if not all(hasattr(e, '_map_dom') for e in bv_exprs):
            raise ValueError(f"{err_prefix}dep must be 'mapped' bound variables, got {dep}")
        if sort is None:
            sort = dom.carT

        ## Do dependency analysis
        #dep_sid_sets= tuple(set(v.sid for v in self.analyze([VarGetter()], d.node, Context(self._envs_obj)).get(VarSet).vars) for d in dep)
        #sids_in_context = set()
        #for i, dep_set in enumerate(dep_sid_sets):
        #    for sid in dep_set:
        #        for dep_sid in self._depends[sid]:
        #            if dep_sid not in sids_in_context:
        #                msg =f"{err_prefix}Variable Dependency Error!\n . bound_var in Dom:{dep[i]} is dependent on {self.sym.get_name(dep_sid)} which is not in context."
        #                raise ValueError(msg)
        #    sids_in_context |= dep_set
        
        public = True
        if name is None:
            name = self._new_var_name()
            public = False
        sid = self.sym.new_var(name, role, public)

        #T = ir.PiT(
        #    grid.cells().node,
        #    ir._LambdaTPlaceholder(
        #        ir._BoundVarPlaceholder(ir.TupleT(ir.IntT(), ir.IntT())), 
        #        opt.Optional(digits).carT
        #    )
        #)
        def make_sort(bves: tp.Tuple[ast.Expr]):
            #if len(bves)>1:
            #    # TODO Almust surely need to modify bv.T to account for dependent bvs
            #    raise NotImplementedError()
            if len(bves)==0:
                return sort
            bv_node = bves[0].node
            bv_dom: ast.DomainExpr = bves[0]._map_dom
            old_T = bves[0].T
            # check if old_T has bvs
            def _has_bv(n: ir.Node):
                if isinstance(n, ir._BoundVarPlaceholder):
                    return True
                return any(_has_bv(c) for c in n._children)
            if _has_bv(old_T):
                raise NotImplementedError("TODO need to handle depenedent types")
            new_bv = ir._BoundVarPlaceholder(old_T)
            T = ir.PiT(
                bv_dom.node,
                ir._LambdaTPlaceholder(
                    new_bv,
                    make_sort(bves[1:])
                )
            )
            return T
        full_sort = make_sort(bv_exprs)
        var = ir._VarPlaceholder(full_sort, sid)
        var = ast.wrap(var)
        # add codom constraint
        if dom is not None:
            def _con(n: int, val):
                if n==0:
                    return dom.contains(val)
                else:
                    return val.forall(lambda v: _con(n-1, v))
            self += _con(len(bvs), var)
        for e in bv_exprs:
            var = var(e)
        return var

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
        ctx = Context(EnvsObj(None, None))
        #pm = PassManager(AstPrinterPass(), KindCheckingPass(), ResolveBoundVars(), verbose=True)
        pm = PassManager(KindCheckingPass(), ResolveBoundVars(), verbose=True)
        rules_node = ir.TupleLit(ir.TupleT(*(ir.BoolT() for _ in self._rules)), *self._rules)
        new_rules_node = pm.run(rules_node, ctx=ctx)
        # Populate tenv
        ctx = Context(EnvsObj(None, None))
        #pm = PassManager(KindCheckingPass(), AstPrinterPass(), ResolveFreeVars(), AstPrinterPass(), verbose=True)
        pm = PassManager(KindCheckingPass(), ResolveFreeVars(), verbose=True)
        new_rules_node = pm.run(new_rules_node, ctx=ctx)
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
        spec.pretty()
        print("PREOPT")
        # 3: Optimize/canonicalize
        spec_opt = spec.optimize()
        print("POSTOPT")
        spec_opt.pretty()
        return spec_opt

    def print(self, rules_node=None):
        if rules_node is None:
            rules_node = ir.TupleLit(ir.TupleT(*(ir.BoolT() for _ in self._rules)), *self._rules)
        ctx = Context()
        pm = PassManager([AstPrinterPass()], verbose=True)
        pm.run(rules_node, ctx)
        a = ctx.get(PrintedAST)
        print(a.text)