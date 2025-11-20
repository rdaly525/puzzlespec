from __future__ import annotations

import typing as tp

from puzzlespec.compiler.passes.envobj import EnvsObj

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir


class PrintedAST(AnalysisObject):
    def __init__(self, text: str):
        self.text = text


class AstPrinterPass(Analysis):
    """Produce a pretty-printed string of the IR with inferred types.

    - One node per line
    - Indentation corresponds to node depth
    - A vertical line segment at each indentation level ("│   ")
    - Each node is annotated with its inferred type

    The result is stored in the context as a `PrintedAST` object and the IR is
    returned unchanged.
    """
    enable_memoization=False
    requires = (EnvsObj,)
    produces = (PrintedAST,)
    name = "ast_printer"

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.envs = ctx.get(EnvsObj)
        self.bctx = []
        self.depth = 0
        rendered = self.visit(root)
        return PrintedAST(rendered)

    def visit(self, node: ir.Node):
        self.depth += 1
        children_strs = self.visit_children(node)
        if len(children_strs)==0:
            print(type(node))
            assert 0
        T_str, children_strs = children_strs[0], children_strs[1:]
        self.depth -= 1
        return self.value_str(node, T_str, children_strs)
 
    def value_str(self, node: ir.Node, T_str, children_strs) -> str:
        fstr = ", ".join([f"{k}={v}" for k,v in node.field_dict.items()])
        if fstr:
            fstr = f"[{fstr}]"
        indent = "|  "*self.depth
        node_prefix = indent + f"{node.__class__.__name__}{fstr}: {T_str}"
        if node.num_children > 1:
            return node_prefix + "(\n" + "\n".join(cs for cs in children_strs) + f"\n{indent})"
        else:
            return node_prefix + "()"
    
    @handles(ir.BoolT, ir.IntT, ir.UnitT, ir.ArrowT, ir.DomT, ir.SumT, ir.TupleT, ir.EnumT, ir.FuncT)
    def _(self, T: ir.Node):
        return str(T)

    @handles(ir.BoundVar)
    def _(self, node: ir.BoundVar):
        T_str = self.bctx[-(node.idx+1)]
        return self.value_str(node, T_str, ())

    @handles(ir.Lambda)
    def _(self, node: ir.Lambda):
        T, body = node._children
        T_str = self.visit(T)
        self.depth +=1
        self.bctx.append(T_str)
        body_str = self.visit(body)
        self.bctx.pop()
        self.depth-=1
        return self.value_str(node, T_str, (body_str,))

    