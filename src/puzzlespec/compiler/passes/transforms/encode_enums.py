from __future__ import annotations

import typing as tp

from ..pass_base import Transform, Context, handles
from ...dsl import ir, ast
from ....libs import var_def, std
from ..envobj import EnvsObj, SymTable

class EncodeEnums(Transform):
    """Encode enums Ints or Bools
    """
    name = "encode_enums"

    requires: tp.Tuple[type, ...] = (EnvsObj,)
    produces: tp.Tuple[type, ...] = (EnvsObj,)

    def __init__(self, as_int: bool = True):
        self.as_int = as_int
        if not self.as_int:
            raise NotImplementedError()
        super().__init__()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        self.sym: SymTable = ctx.get(EnvsObj).sym.copy()
        new_root = self.visit(root)
        env = EnvsObj(self.sym)
        return new_root, env

    #@handles(ir.VarRef)
    #def _(self, node: ir.VarRef) -> ir.Node:
    #    T, = self.visit_children(node)
    #    if isinstance(T, ir.EnumT):
    #        assert node.sid in self.sym
    #        e = self.sym[node.sid]
    #        n = len(T)
    #        #Special case n==2
    #        if n>2:
    #            new_name = f"_E{e.name}_I{n}"
    #            new_sid = self.sym.new_var(new_name, metadata=e._metadata)
    #            T = ir.IntT()
    #            new_var = ir.VarRef(new_sid)
    #            obl = ir.IsMember(
    #                ir.BoolT(),
    #                ir.Fin(ir.DomT.make(ir.IntT(), fin=True, ord=True), ir.Lit(ir.IntT(), val=n)),
    #                new_var
    #            )
    #            self.obls[new_sid] = obl
    #        else:
    #            assert n==2
    #            new_name = f"_E{e.name}_B"
    #            new_sid = self.sym.new_var(new_name, e.role, e.public)
    #            T = ir.BoolT()
    #            new_var = ir.VarRef(new_sid)
    #        return new_var
    #    return node.replace(T)
    
    @handles(ir.EnumLit)
    def _(self, node: ir.EnumLit) -> ir.Node:
        enumT = node.T
        T, = self.visit_children(node)
        assert isinstance(enumT, ir.EnumT)
        n = len(enumT)
        i = enumT.labels.index(node.label)
        if n==2:
            return ir.Lit(T, val=bool(i))
        else:
            return ir.Lit(T, val=i)

    #@handles(ir.Universe)
    #def _(self, node: ir.Universe) -> ir.Node:
    #    T, = self.visit_children(node)
    #    carT = T.carT
    #    if isinstance(carT, ir.EnumT):
    #        n = len(node.T.carT)
    #        assert n>=2
    #        if n==2:
    #            return ir.Universe(ir.DomT.make(ir.BoolT(), fin=True, ord=True))
    #        else:
    #            fin = ir.Fin(ir.DomT.make(ir.IntT(), fin=True, ord=True), ir.Lit(ir.IntT(), val=n))
    #            return fin
    #    return node.replace(T)

    @handles(ir.EnumT)
    def _(self, node: ir.EnumT) -> ir.Node:
        n = len(node)
        if len(node)==2:
            return ir.BoolT()
        else:
            return ir.RefT(
                ir.IntT(),
                std.fin(n).node
            )