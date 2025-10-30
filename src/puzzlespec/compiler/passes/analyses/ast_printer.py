from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context
from ..analyses.sym_table import SymTableEnv_
from ...dsl import ir, ir_types as irT


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

    requires = ()
    produces = (PrintedAST,)
    name = "ast_printer"

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.depth = 0
        rendered = self.visit(root)
        return PrintedAST(rendered)

    def visit(self, node: ir.Node) -> None:
        self.depth += 1
        children_strs = self.visit_children(node)
        self.depth -= 1
        fstr = ", ".join([f"{k}={v}" for k,v in node.field_dict.items()])
        if fstr:
            fstr = f"[{fstr}]"
        indent = "|  "*self.depth
        node_prefix = indent + f"{node.__class__.__name__}{fstr}"
        if node.num_children > 0:
            return node_prefix + "(\n" + "\n".join(cs for cs in children_strs) + f"\n{indent})"
        else:
            return node_prefix + "()"