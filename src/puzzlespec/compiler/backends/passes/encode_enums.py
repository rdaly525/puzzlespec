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

    @handles(ir.Lit)
    def _(self, node: ir.Lit) -> ir.Node:
        if isinstance(node.T, ir.EnumT):
            enumT = node.T
            vc = self.visit_children(node)
            T = vc.T
            assert isinstance(enumT, ir.EnumT)
            n = len(enumT)
            i = enumT.labels.index(node.label)
            if n==2:
                return ir.Lit(T, val=bool(i))
            else:
                return ir.Lit(T, val=i)

    @handles(ir.EnumT)
    def _(self, node: ir.EnumT) -> ir.Node:
        n = len(node)
        if len(node)==2:
            return ir.BoolT()
        else:
            return ir.IntT(ref=std.fin(n).node)
