from __future__ import annotations

import typing as tp

from ..pass_base import Transform, Context, handles
from ..transforms.beta_reduction import beta_reduce
from ...dsl import ir, utils
from ..envobj import EnvsObj, TypeEnv, SymTable, OblsObj
from ...dsl.envs import SymEntry

class ScalarizeVars(Transform):
    """Scalarize vars
    """
    name = "scalarize_vars"

    requires: tp.Tuple[type, ...] = (EnvsObj,)
    produces: tp.Tuple[type, ...] = (EnvsObj, OblsObj)

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        self.tenv: TypeEnv = ctx.get(EnvsObj).tenv.copy()
        self.sym: SymTable = ctx.get(EnvsObj).sym.copy()
        self.obls: tp.Mapping[int, ir.Node] = {}
        new_root = self.visit(root)
        return new_root, EnvsObj(self.sym, self.tenv), OblsObj(self.obls)


    def make_var(self, T: ir.Type, prefix: str, e: SymEntry):
        if isinstance(T, (ir.EnumT, ir.IntT, ir.BoolT)):
            char = "E" if isinstance(T, ir.EnumT) else "I" if isinstance(T, ir.IntT) else "B"
            new_name = f"{prefix}_{char}"
            new_sid = self.sym.new_var(new_name, e.role, e.public)
            self.tenv.add(new_sid, T)
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
            dom, piT = T._children
            dom_size = utils._dom_size(dom)
            if dom_size is None:
                raise ValueError(f"Expected finite domain, got {dom}")
            val_map = {}
            terms = []
            for i, dval in enumerate(utils._iterate(dom)):
                if dval is None:
                    raise ValueError(f"Expected domain element, got {dval}")

                appT = ir.ApplyT(piT, dval)
                resT = beta_reduce(appT)
                new_var = self.make_var(resT, f"{prefix}_F{i}", e)
                val_map[dval._key] = i
                terms.append(new_var)
            return ir.FuncLit(T, dom, *terms, layout=ir._DenseLayout(val_map=val_map))
        raise ValueError(f"Expected scalar type, got {T}")
    
    @handles(ir.VarRef)
    def _(self, node: ir.VarRef) -> ir.Node:
        T = self.tenv[node.sid]
        e = self.sym[node.sid]
        # Base case (enum, bool, int)
        if isinstance(T, (ir.EnumT, ir.IntT, ir.BoolT)):
            return node
        return self.make_var(T, e.name, e)
