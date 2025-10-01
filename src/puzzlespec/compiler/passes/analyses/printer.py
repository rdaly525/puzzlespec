from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context
from ...dsl import ir, ir_types as irT
from .type_inference import TypeValues


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

    requires = (TypeValues,)
    produces = (PrintedAST,)
    name = "ast_printer"

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self._types: tp.Dict[ir.Node, irT.Type_] = ctx.get(TypeValues).mapping
        lines: tp.List[str] = []
        self._emit_lines(root, 0, lines)
        rendered = "\n".join(lines)
        return PrintedAST(rendered)

    def _emit_lines(self, node: ir.Node, depth: int, out_lines: tp.List[str]) -> None:
        prefix = "" if depth == 0 else ("│   " * depth)
        label = self._format_node_label(node)
        out_lines.append(f"{prefix}{label}")
        for child in node:
            self._emit_lines(child, depth + 1, out_lines)

    def _format_node_label(self, node: ir.Node) -> str:
        # Node class name and any declarative fields for helpful context
        cls_name = node.__class__.__name__
        field_snippets: tp.List[str] = []
        for field in getattr(node, "_fields", ()):
            try:
                value = getattr(node, field)
            except Exception:
                value = "?"
            field_snippets.append(f"{field}={value}")
        if field_snippets:
            cls_repr = f"{cls_name}({', '.join(field_snippets)})"
        else:
            cls_repr = cls_name

        T = self._types.get(node)
        type_repr = repr(T) if T is not None else "?"
        return f"{cls_repr} : {type_repr}"


