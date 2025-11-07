import typing as tp

from puzzlespec.compiler.passes.transforms.resolve_bound_vars import ResolveBoundVars
from . import ast, ir, ir_types as irT
from .envs import SymTable, DomEnv, TypeEnv
from ..passes.pass_base import Context
from ..passes.transforms.cse import CSE
from ..passes.analyses.getter import VarGetter, VarSet
from ..passes.analyses import EnvsObj
from .spec import PuzzleSpec

class PuzzleSpecBuilder(PuzzleSpec):
    def __init__(self):
        super().__init__("", "", SymTable(), TypeEnv(), DomEnv(), [], [])
        self._name_name_cnt = 0
        # sid -> "sids which key depends on"
        self._depends = {}

    @property
    def rules(self) -> ast.TupleExpr:
        return tp.cast(ast.TupleExpr, ast.wrap(self.rules_node, irT.TupleT((irT.Bool,)*len(self._rules))))

    @property
    def obligations(self) -> ast.TupleExpr:
        return tp.cast(ast.TupleExpr, ast.wrap(self.obligations_node, irT.TupleT((irT.Bool,)*len(self._obligations))))

    @property
    def _envs_obj(self) -> EnvsObj:
        return EnvsObj(sym=self.sym, tenv=self.tenv, domenv=self.domenv)

    def _new_var_name(self):
        self._var_name_cnt += 1
        return f"_X{self._var_name_cnt}"

    # Core idea: Only allow vars with deps constructed via tabulate. In a tabulate, I can throw the domain/domT inside the bound var placeholder.
    # This now gives me the tabulated domains asociated with the bound var and therefore I can eagerly construct the nested Func var
    def var(self, 
        role: str='D', 
        sort: tp.Optional[irT.Type_]=None, 
        dom: tp.Optional[ast.DomainExpr]=None, 
        name: tp.Optional[str]=None, 
        dep: tp.Optional[tp.Tuple[ast.Expr, ...]]=None
    ) -> ast.Expr:
        err_prefix=f"ERROR In var {name}: "
        if dom is not None and not isinstance(dom, ast.DomainExpr):
            raise ValueError(f"{err_prefix}dom must be a DomainExpr, got {type(dom)}")
        if sort is not None and not isinstance(sort, irT.Type_):
            raise ValueError(f"{err_prefix}sort must be a Type_, got {type(sort)}")
        if role not in "GDP":
            raise ValueError(f"{err_prefix}role must be G, P, or D, got {role}")
        if sort is None and dom is None:
            raise ValueError(f"{err_prefix}Either dom or sort must be provided")
        if dom is not None and sort is not None and dom.carT:
            raise ValueError(f"{err_prefix}dom.carT must be equal to sort, got {dom.carT} and {sort}")
        if dom is None:
            dom = ast.wrap(ir.Universe(sort), irT.DomT(sort))
        dom_obl = dom
        if not isinstance(dep, tp.Tuple):
            dep = (dep,)
        if not all(isinstance(d.node, ir._BoundVarPlaceholder) for d in dep):
            raise ValueError(f"{err_prefix}dep must be bound variables, got {type(dep)}")
        dep_dom_nodes = tuple(d.node.dom for d in dep)
        dep_domTs = tuple(irT.DomT(d.node.T) for d in dep)
        assert all(isinstance(domT, irT.DomT) for domT in dep_domTs)
        if not all(n.is_tabulate for n in dep_dom_nodes):
            raise NotImplementedError(f"{err_prefix}Only DomExpr.tabulate dependencies are supported")
       
        # Do dependency analysis
        dep_sid_sets= tuple(set(v.sid for v in self.analyze([VarGetter()], d.node, Context(self._envs_obj)).get(VarSet).vars) for d in dep)
        sids_in_context = set()
        for i, dep_set in enumerate(dep_sid_sets):
            for sid in dep_set:
                for dep_sid in self._depends[sid]:
                    if dep_sid not in sids_in_context:
                        msg =f"{err_prefix}Variable Dependency Error!\n . bound_var in Dom:{dep[i]} is dependent on {self.sym.get_name(dep_sid)} which is not in context."
                        raise ValueError(msg)
            sids_in_context |= dep_set
        
        public = True
        if name is None:
            name = self._new_var_name()
            public = False
        
        new_sid = self.sym.new_var(name, role, public)

        self._depends[new_sid] = sids_in_context
        
        # update domain env
        self.domenv.add(
            sid=new_sid,
            dom_nodes = dep_dom_nodes,
            dom_Ts = dep_domTs,
        )

        # Calc T
        T = dom.carT
        for domT in reversed(dep_domTs):
            T = irT.FuncT(domT, T)
        self.tenv.add(sid, T)
        
        #Calculate expr of var
        var = tp.cast(T, ast.wrap(ir.VarRef(new_sid), T))
        for d in dep:
            var = var.apply(d)

        # Add obligations
        def oblig(val:ast.Expr, doms:tp.Tuple)->ast.Expr:
            if doms==():
                return val in dom_obl
            return doms[0].forall(lambda i: oblig(val.apply(i), doms[1:]))
        self._obligations.append(oblig(var, dep))
        return var

    def param(self, sort: irT.Type_=None, dom: ast.DomainExpr=None, name: str=None, dep=()) -> ast.Expr:
        return self.var(sort=sort, dom=dom, name=name, dep=dep)
    
    def gen_var(self, sort: irT.Type_=None, dom: ast.DomainExpr=None, name: str=None, dep=()) -> ast.Expr:
        return self.var(sort=sort, dom=dom, name=name, dep=dep)
    
    def decision_var(self, sort: irT.Type_=None, dom: ast.DomainExpr=None, name: str=None, dep=()) -> ast.Expr:
        return self.var(sort=sort, dom=dom, name=name, dep=dep)

    def func_var(self, dom: ast.DomainExpr, role: str='G', sort: irT.Type_=None, codom: ast.DomainExpr=None, name: str=None) -> ast.Expr:
        return dom.tabulate(lambda i: self.var(role, sort, codom, name, dep=i))

    def _replace_rules(self, new_rules: tp.Iterable[ir.Node]):
        self._rules = new_rules
 
    def _add_rules(self, *new_rules: ast.Expr):
        nodes = [*self._rules._children, *[r.node for r in new_rules]]
        self._replace_rules(nodes)

    def __iadd__(self, other: tp.Union[ast.BoolExpr, tp.Iterable[ast.BoolExpr]]) -> tp.Self:
        
        constraints = other
        if not isinstance(other, tp.Iterable):
            constraints = [other]

        # Verify that all the constraints bool expressions    
        if not all(isinstance(c, ast.BoolExpr) for c in constraints):
            raise ValueError(f"Constraints, {constraints}, is not a BoolExpr")
        
        self._add_rules(*constraints)

        self._type_check()
        return self

    # Freezes the spec and makes it immutable 
    def build(self, name: str, desc: str) -> PuzzleSpec:
        # 1: Resolve Placeholders (for bound bars/lambdas)
        spec = self.transform([ResolveBoundVars()])
        # 2: Run CSE
        spec = self.transform([CSE()])

        return spec.optimize()