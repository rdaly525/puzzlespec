from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir

def print_ast(node: ir.Node):
    obj = AstPrinterPass()(node, Context())
    return obj.text

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
    requires = () #(EnvsObj,)
    produces = (PrintedAST,)
    name = "ast_printer"
    enable_memoization=False

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.depth = 0
        rendered = self.visit(root)
        return PrintedAST(rendered)
    
    def visit(self, node: ir.Node):
        indent = "| " * self.depth
        fstr = ", ".join([f"{k}={v}" for k, v in node.field_dict.items()])
        if fstr:
            fstr = f"[{fstr}]"
        node_prefix = indent + f"{node.__class__.__name__}{fstr}: {str(node._hash)[-5:]}"
        self.depth += 1

        parts = []
        if isinstance(node, ir.Value):
            vc = self.visit_children(node)
            T_str = self.visit(node.T)
            parts.append(f"{indent}| T={T_str}")
            for i, c in enumerate(node._children):
                parts.append(self.visit(c))
            if vc.obl is not None:
                obl_str = self.visit(node.obl)
                parts.append(f"{indent}| obl={obl_str}")
        elif isinstance(node, ir.Type):
            vc = self.visit_children(node)
            for c in node._children:
                parts.append(self.visit(c))
            if vc.ref is not None:
                ref_str = self.visit(node.ref)
                parts.append(f"{indent}| ref={ref_str}")
            if vc.view is not None:
                view_str = self.visit(node.view)
                parts.append(f"{indent}| view={view_str}")
            if vc.obl is not None:
                obl_str = self.visit(node.obl)
                parts.append(f"{indent}| obl={obl_str}")
        else:
            for c in node._children:
                parts.append(self.visit(c))

        if parts:
            s = node_prefix + "(\n" + "\n".join(parts) + f"\n{indent})"
        else:
            s = node_prefix + "()"
        self.depth -= 1
        return s