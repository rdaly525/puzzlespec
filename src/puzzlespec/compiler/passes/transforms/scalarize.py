from __future__ import annotations

import typing as tp

from ..pass_base import Transform, Context, handles
from ..transforms.beta_reduction import beta_reduce
from ...dsl import ir, utils
from ..envobj import EnvsObj, SymTable, OblsObj
from ...dsl.envs import SymEntry

class Scalarize(Transform):
    """Scalarize everything
    """
    name = "scalarize"

    requires: tp.Tuple[type, ...] = (EnvsObj,)
    produces: tp.Tuple[type, ...] = (EnvsObj, OblsObj)

    def __init__(self, max_dom_size: int = 100, aggressive: bool = False):
        self.max_dom_size = max_dom_size
        self.aggressive = aggressive

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        self.sym: SymTable = ctx.get(EnvsObj).sym.copy()
        self.obls: tp.Mapping[int, ir.Node] = {}
        new_root = self.visit(root)
        return new_root, EnvsObj(self.sym, self.tenv), OblsObj(self.obls)

    def make_var(self, T: ir.Type, prefix: str, e: SymEntry):
        if isinstance(T, (ir.EnumT, ir.IntT, ir.BoolT)):
            char = "E" if isinstance(T, ir.EnumT) else "I" if isinstance(T, ir.IntT) else "B"
            new_name = f"{prefix}_{char}"
            new_sid = self.sym.new_var(new_name, e.role, e.public)
            return ir.VarRef(new_sid)
        if isinstance(T, ir.TupleT):
            elems = []
            for i, elemT in enumerate(T._children):
                elems.append(self.make_var(elemT, f"{prefix}_T{i}", e))
            return ir.TupleLit(T, *elems)
        if isinstance(T, ir.SumT):
            # Create tag variable (IntT) with obligation that it's in Fin(len(elemTs))
            tag_var = self.make_var(ir.IntT(), f"{prefix}_Stag", e)
            # Add obligation: tag ∈ Fin(len(elemTs))
            n = len(T.elemTs)
            fin_dom = ir.Fin(ir.DomT.make(ir.IntT(), fin=True, ord=True), ir.Lit(ir.IntT(), val=n))
            # tag_var should be a VarRef from make_var
            assert isinstance(tag_var, ir.VarRef)
            obl = ir.IsMember(ir.BoolT(), fin_dom, tag_var)
            self.obls[tag_var.sid] = obl
            # Recursively create variables for each variant
            elems = []
            for i, elemT in enumerate(T.elemTs):
                elems.append(self.make_var(elemT, f"{prefix}_S{i}", e))
            return ir.SumLit(T, tag_var, *elems)
        if isinstance(T, ir.FuncT):
            dom, lamT = T._children
            dom_size = utils._dom_size(dom)
            if dom_size is None:
                raise ValueError(f"Expected finite domain, got {dom}")
            val_map = {}
            terms = []
            for i, dval in enumerate(utils._iterate(dom)):
                if dval is None:
                    raise ValueError(f"Expected domain element, got {dval}")

                appT = ir.ApplyT(lamT, dval)
                resT = beta_reduce(appT)
                new_var = self.make_var(resT, f"{prefix}_F{i}", e)
                val_map[dval._key] = i
                terms.append(new_var)
            return ir.FuncLit(T, dom, *terms, layout=ir._DenseLayout(val_map=val_map))
        raise ValueError(f"Expected scalar type, got {T}")
    
    @handles(ir.VarRef)
    def _(self, node: ir.VarRef) -> ir.Node:
        T, = self.visit_children(node)
        e = self.sym[node.sid]
        # Base case (enum, bool, int)
        if isinstance(T, (ir.EnumT, ir.IntT, ir.BoolT)):
            return node
        return self.make_var(T, e.name, e)

    @handles(ir.Map)
    def _(self, node: ir.Map):
        T, dom, lam = self.visit_children(node)
        dom_size = utils._dom_size(dom)
        doit = self.aggressive or not utils._has_freevar(lam)
        if dom_size is not None and dom_size <= self.max_dom_size and doit:
            # Convert Map to FuncLit by evaluating lambda for each domain element
            elems = []
            val_map = {}
            for i, v in enumerate(utils._iterate(dom)):
                assert v is not None
                # Apply lambda and visit to simplify
                val = ir.Apply(T.piT.resT, lam, v)
                val = self.visit(val)
                elems.append(val)
                val_map[v._key] = i
            layout = ir._DenseLayout(val_map=val_map)
            return ir.FuncLit(T, dom, *elems, layout=layout)
        return node.replace(T, dom, lam)


    @handles(ir.Forall)
    def _(self, node: ir.Forall):
        T, func = self.visit_children(node)
        # Extract domain and lambda from func if it's a Map
        if isinstance(func, ir.FuncLit):
            _, dom, *vals = func._children
            dom_size = utils._dom_size(dom)
            if dom_size is not None and dom_size <= self.max_dom_size:
                conj_vals = []
                for v in utils._iterate(dom):
                    assert v is not None
                    i = func.layout.index(v)
                    assert i is not None and 0 <= i < len(vals)
                    conj_vals.append(vals[i])
                return ir.Conj(T, *conj_vals)

        return node.replace(T, func)

    @handles(ir.Exists)
    def _(self, node: ir.Exists):
        T, func = self.visit_children(node)
        # Extract domain and lambda from func if it's a Map
        if isinstance(func, ir.FuncLit):
            _, dom, *vals = func._children
            disj_vals = []
            for v in utils._iterate(dom):
                assert v is not None
                i = func.layout.index(v)
                assert i is not None and 0 <= i < len(vals)
                disj_vals.append(vals[i])
            return ir.Disj(T, *disj_vals)
        return node.replace(T, func)

    @handles(ir.Restrict)
    def _(self, node: ir.Restrict):
        T, func = self.visit_children(node)
        # Extract domain and predicate values from func if it's a FuncLit
        if isinstance(func, ir.FuncLit):
            _, dom, *vals = func._children
            dom_size = utils._dom_size(dom)
            if dom_size is not None and dom_size <= self.max_dom_size:
                # Early out: check that all predicate values are literals
                if not all(isinstance(v, ir.Lit) for v in vals):
                    return node.replace(T, func)
                restricted_elems = []
                for v in utils._iterate(dom):
                    assert v is not None
                    i = func.layout.index(v)
                    assert i is not None and 0 <= i < len(vals)
                    pred_val = vals[i]
                    # Only include elements where predicate is True
                    if isinstance(pred_val.T, ir.BoolT) and pred_val.val is True:
                        restricted_elems.append(v)
                # Create DomLit with the restricted elements
                return ir.DomLit(T, *restricted_elems)
        return node.replace(T, func)

    @handles(ir.SumLit)
    def _(self, node: ir.SumLit):
        T, tag, *elems = self.visit_children(node)
        # If tag is a literal IntT, convert to Inj
        if isinstance(tag, ir.Lit) and isinstance(tag.T, ir.IntT):
            tag_val = tag.val
            assert isinstance(tag_val, int) and 0 <= tag_val < len(elems)
            return ir.Inj(T, elems[tag_val], idx=tag_val)
        return node.replace(T, tag, *elems)

