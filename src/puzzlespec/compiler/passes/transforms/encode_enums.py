from __future__ import annotations

import typing as tp

from ..pass_base import Transform, Context, handles
from ...dsl import ir
from ..envobj import EnvsObj, TypeEnv, SymTable, OblsObj

class EncodeEnums(Transform):
    """Encode enums Ints or Bools
    """
    name = "encode_enums"

    requires: tp.Tuple[type, ...] = (EnvsObj,)
    produces: tp.Tuple[type, ...] = (EnvsObj, OblsObj)

    def __init__(self, as_int: bool = True):
        self.as_int = as_int
        self.obls: tp.Mapping[int, ir.Node] = {}
        super().__init__()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        self.tenv: TypeEnv = ctx.get(EnvsObj).tenv.copy()
        self.sym: SymTable = ctx.get(EnvsObj).sym.copy()
        self.obls: tp.Mapping[int, ir.Node]
        new_root = self.visit(root)
        env = EnvsObj(self.sym, self.tenv)
        obls = OblsObj(self.obls)
        return new_root, env, obls

    @handles(ir.VarRef)
    def _(self, node: ir.VarRef) -> ir.Node:
        T = self.tenv[node.sid]
        e = self.sym[node.sid]
        if not isinstance(T, ir.EnumT):
            return node
        n = len(T)
        #Special case n==2
        if n>2:
            new_name = f"_E{e.name}_I{n}"
            new_sid = self.sym.new_var(new_name, e.role, e.public)
            T = ir.IntT()
            self.tenv.add(new_sid, T)
            new_var = ir.VarRef(new_sid)
            obl = ir.IsMember(
                ir.BoolT(),
                ir.Fin(ir.DomT.make(ir.IntT(), fin=True, ord=True), ir.Lit(ir.IntT(), val=n)),
                new_var
            )
            self.obls[new_sid] = obl
        else:
            assert n==2
            new_name = f"_E{e.name}_B"
            new_sid = self.sym.new_var(new_name, e.role, e.public)
            T = ir.BoolT()
            self.tenv.add(new_sid, T)
            new_var = ir.VarRef(new_sid)
        return new_var
    
    @handles(ir.EnumLit)
    def _(self, node: ir.EnumLit) -> ir.Node:
        T = node.T
        assert isinstance(T, ir.EnumT)
        i = T.labels.index(node.label)
        if len(T)==2:
            return ir.Lit(ir.BoolT(), val=bool(i))
        else:
            return ir.Lit(ir.IntT(), val=i)

    @handles(ir.Universe)
    def _(self, node: ir.Universe) -> ir.Node:
        if isinstance(node.T.carT, ir.EnumT):
            if len(node.T.carT)==2:
                return ir.Universe(ir.DomT.make(ir.Bool(), fin=True, ord=True))
            else:
                fin = ir.Fin(ir.DomT.make(ir.IntT(), fin=True, ord=True), ir.Lit(ir.IntT(), val=len(node.T.carT)))
                return fin
        return node.replace(*self.visit_children(node))

    @handles(ir.EnumT)
    def _(self, node: ir.EnumT) -> ir.Node:
        if len(node)==2:
            return ir.BoolT()
        else:
            return ir.IntT()