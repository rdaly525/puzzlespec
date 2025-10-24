from __future__ import annotations

import typing as tp
from ..pass_base import Transform, Context, handles, AnalysisObject
from ...dsl import ir, ir_types as irT
import itertools as it

class TypeEncoding(AnalysisObject):
    def __init__(self, c_encoding: irT.Type_):
        # Can only handle Int or Tuple[Int, Int] for now
        if not c_encoding in (irT.Int, irT.CellIdxT_RC):
            raise ValueError(f"Unsupported encoding: {c_encoding}")
        self.c_encoding = c_encoding
    
    def replace_type(self, T: irT.Type_) -> irT.Type_:
        match T:
            case irT.CellIdxT:
                return self.c_encoding
            case irT.DictT(keyT, valT):
                return irT.DictT(self.replace_type(keyT), self.replace_type(valT))
            case irT.TupleT(Ts):
                return irT.TupleT(*[self.replace_type(T) for T in Ts])
            case irT.ListT(elemT):
                return irT.ListT(self.replace_type(elemT))
            case irT.GridT(valueT, mode):
                return irT.GridT(self.replace_type(valueT), mode)
            case irT.ArrowT(argT, resT):
                return irT.ArrowT(self.replace_type(argT), self.replace_type(resT))
            case _:
                return T

# This will convert all abstract types (e.g. CellIdx) to concrete types (e.g. Int)
class ConcretizeTypes(Transform):

    requires = (TypeEncoding,)  # Add required analysis dependencies here
    name = "concretize_types"

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        """Main entry point for the transform pass."""
        self.type_encoding: TypeEncoding = ctx.get(TypeEncoding)
        return self.visit(root)

    # Nodes that touch CellIdxT: GridEnumNode, Lambda

    @handles()
    def _(self, node: ir.Lambda) -> ir.Node:
        body, = self.visit_children(node)
        paramT = self.type_encoding.replace_type(node.paramT)
        return ir.Lambda(body, paramT=paramT)

    @handles(ir.GridEnumNode)
    def _(self, node: ir.GridEnumNode) -> ir.Node:
        nR, nC = self.visit_children(node)
        if nR.is_lit and nC.is_lit:
            mode = node.mode
            mk = lambda r,c: ir.Tuple(ir.Lit(r, irT.Int),ir.Lit(c, irT.Int))
            match mode:
                case "Cells":
                    return ir.List(*[mk(r,c) for r,c in it.product(range(nR.val), range(nC.val))])
                case "Rows":
                    return ir.List(
                        *[ir.List(*[mk(r,c) for c in range(nC.val)]) for r in range(nR.val)]
                    )
                case "Cols":
                    return ir.List(
                        *[ir.List(*[mk(r,c) for r in range(nR.val)]) for c in range(nC.val)]
                    )
        return node.replace(nR, nC)