
# ---- Views, Isomorphisms, Domains, Abstractions (compiler metadata) ----

@dataclass
class ViewNode:
    name: str
    kind: tp.Literal["primary_var", "iso_var", "domain", "abstract"]
    of: tp.Optional[str]
    type: irT.Type_


@dataclass
class IsoEdge:
    a: str
    b: str
    to_b: ast.Expr  # LambdaExpr captured as Expr for now
    to_a: ast.Expr


@dataclass
class AbsEdge:
    concrete: str
    abstract: str
    alpha: ast.Expr  # LambdaExpr
    gamma: ast.Expr  # LambdaExpr


@dataclass
class DomEdge:
    var: str
    dom: str


class ViewGraph:
    def __init__(self):
        self.nodes: tp.Dict[str, ViewNode] = {}
        self.isos: tp.List[IsoEdge] = []
        self.abss: tp.List[AbsEdge] = []
        self.doms: tp.List[DomEdge] = []

    def add_primary(self, name: str, type_: irT.Type_) -> None:
        self.nodes[name] = ViewNode(name=name, kind="primary_var", of=None, type=type_)

    def add_isomorphism(self, a: str, b: str, to_b: ast.Expr, to_a: ast.Expr) -> None:
        # Register both nodes if missing
        if a not in self.nodes:
            raise ValueError(f"Primary/iso view '{a}' must be declared before adding isomorphism")
        if b not in self.nodes:
            # Assume iso var type matches image of to_b; store as iso_var of a
            self.nodes[b] = ViewNode(name=b, kind="iso_var", of=a, type=self.nodes[a].type)
        self.isos.append(IsoEdge(a=a, b=b, to_b=to_b, to_a=to_a))

    def add_domain(self, var: str, dom: str, type_: irT.Type_) -> None:
        if var not in self.nodes:
            raise ValueError(f"Variable view '{var}' must exist before adding domain")
        self.nodes[dom] = ViewNode(name=dom, kind="domain", of=var, type=type_)
        self.doms.append(DomEdge(var=var, dom=dom))

    def add_abstraction(self, concrete: str, abstract: str, alpha: ast.Expr, gamma: ast.Expr, abs_type: irT.Type_) -> None:
        if concrete not in self.nodes:
            raise ValueError(f"Concrete view '{concrete}' must exist before abstraction")
        self.nodes[abstract] = ViewNode(name=abstract, kind="abstract", of=concrete, type=abs_type)
        self.abss.append(AbsEdge(concrete=concrete, abstract=abstract, alpha=alpha, gamma=gamma))

    def is_primary(self, name: str) -> bool:
        node = self.nodes.get(name)
        return node is not None and node.kind == "primary_var"

    # Placeholder: structural canonicalization hook
    def canonicalize(self, expr: ast.Expr) -> ast.Expr:
        return expr


def emit_var_domain_channel(var: ast.Expr, dom: ast.ListExpr[ast.Expr]) -> tp.List[ast.BoolExpr]:
    """Return the standard channeling constraints between a variable value and its domain list.

    1) var=v ⇒ contains(dom, v)
    2) var=v ⇒ ∀w≠v: ¬contains(dom, w)
    3) ¬contains(dom, w) ⇒ var≠w
    4) len(dom)=1 ⇒ var=only_element(dom)
    """
    # Types are intentionally generic; caller ensures consistent types
    v = ast.wrap(ir.BoundVar(), var.T)
    w = ast.wrap(ir.BoundVar(), var.T)

    # 1) ∀v. (var==v) ⇒ dom.contains(v)
    c1 = ast.BoolExpr(ir.Forall(ir.ListTabulate(ir.ListLength(dom.node), ir.Lambda(ir.BoundVar(), v.node)),
                                ir.Implies(ir.Eq(var.node, v.node), ir.ListContains(dom.node, v.node))), irT.Bool)

    # 2) ∀v. (var==v) ⇒ ∀w!=v. ¬contains(dom, w)
    inner = ir.Forall(ir.ListTabulate(ir.ListLength(dom.node), ir.Lambda(ir.BoundVar(), w.node)),
                      ir.Implies(ir.Not(ir.Eq(w.node, v.node)), ir.Not(ir.ListContains(dom.node, w.node))))
    c2 = ast.BoolExpr(ir.Forall(ir.ListTabulate(ir.ListLength(dom.node), ir.Lambda(ir.BoundVar(), v.node)),
                                ir.Implies(ir.Eq(var.node, v.node), inner)), irT.Bool)

    # 3) ∀w. ¬contains(dom, w) ⇒ var!=w
    c3 = ast.BoolExpr(ir.Forall(ir.ListTabulate(ir.ListLength(dom.node), ir.Lambda(ir.BoundVar(), w.node)),
                                ir.Implies(ir.Not(ir.ListContains(dom.node, w.node)), ir.Not(ir.Eq(var.node, w.node)))), irT.Bool)

    # 4) ListLength(dom)=1 ⇒ var==OnlyElement(dom)
    c4 = ast.BoolExpr(ir.Implies(ir.Eq(ir.ListLength(dom.node), ir.Lit(1)), ir.Eq(var.node, ir.OnlyElement(dom.node))), irT.Bool)

    return [c1, c2, c3, c4]

    def print_rules(self):
        for rule in self.rules:
            ir.pretty_print(rule.node)

    # --- Introspection helpers for tactics ---
    def get_vars_by_role(self, role: tp.Optional[str] = None) -> tp.List[ast.Expr]:
        out: tp.List[ast.Expr] = []
        for name, expr in self._exprs.items():
            if role is None or self.renv.roles.get(name) == role:
                out.append(expr)
        return out

    def get_var_dicts(self, role: tp.Optional[str] = None) -> tp.List[ast.DictExpr[ast.Expr, irT.Type_]]:
        res: tp.List[ast.DictExpr[ast.Expr, irT.Type_]] = []
        for expr in self.get_vars_by_role(role):
            if isinstance(expr.T, irT.DictT):
                res.append(tp.cast(ast.DictExpr[ast.Expr, irT.Type_], expr))
        return res