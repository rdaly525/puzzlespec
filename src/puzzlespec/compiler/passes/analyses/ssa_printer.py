from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ..envobj import EnvsObj, SymTable
from ...dsl import ir, ast

class UsesResult(AnalysisObject):
    def __init__(self, use_cnt):
        self.use_cnt = use_cnt

class Uses(Analysis):
    produces = (UsesResult,)

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        """Main entry point for the analysis pass."""
        self.use_cnt = {root: 1}
        self.visit(root)
        return UsesResult(self.use_cnt)

    def visit(self, node: ir.Node) -> tp.Any:
        self.visit_children(node)
        for c in node.all_nodes:
            if c in self.use_cnt:
                self.use_cnt[c] += 1
            else:
                self.use_cnt[c] = 1

def print_ssa(node: ir.Node):
    text = SSAPrinter()(node, Context()).text
    print(text)

class SSAResult(AnalysisObject):
    def __init__(self, text):
        self.text = text

class SSAPrinter(Analysis):
    """
    Creates a python AST object that is a 'serialization' of a SpecObject
    This will be in SSA form and will look something like:

    """

    requires = ()  
    produces = (SSAResult,)  
    name = "ssa_printer"
    enable_memoization=False

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.tcnt = 0
        self.vcnt = 0
        self.vmap = {}
        self.decls = []
        res = self.visit(root)
        text = "\n" + "\n".join(self.decls) + "\n"
        return SSAResult(text)

    def new_var(self, node: ir.Node):
        if isinstance(node, ir.Type):
            v = f"t{self.tcnt}"
            self.tcnt += 1
        else:
            v = f"x{self.vcnt}"
            self.vcnt += 1
        return v

    def visit(self, node: ir.Node):
        if node not in self.vmap:
            vc = self.visit_children(node)
            vname = self.new_var(node)
            fstr = ""
            if len(node.field_dict) > 0:
                fstr = "[" + ", ".join(f"{k}={v}" for k,v in node.field_dict.items()) + "]"
            if isinstance(node, ir.Value):
                T_str = self.visit(node.T) if node.T not in self.vmap else self.vmap[node.T]
                cs = ", ".join(str(self.visit(c) if c not in self.vmap else self.vmap[c]) for c in node._children)
                decl = f"{vname}: {T_str} = {node.__class__.__name__}{fstr}({cs})"
                if vc.obl is not None:
                    obl_str = self.visit(node.obl) if node.obl not in self.vmap else self.vmap[node.obl]
                    decl += f" # obl={obl_str}"
            elif isinstance(node, ir.Type):
                cs = ", ".join(str(self.visit(c) if c not in self.vmap else self.vmap[c]) for c in node._children)
                ref_str = ""
                if vc.ref is not None:
                    ref_v = self.visit(node.ref) if node.ref not in self.vmap else self.vmap[node.ref]
                    ref_str = f": {ref_v}"
                decl = f"{vname}{ref_str} = {node.__class__.__name__}{fstr}({cs})"
                comment_parts = []
                if vc.view is not None:
                    view_v = self.visit(node.view) if node.view not in self.vmap else self.vmap[node.view]
                    comment_parts.append(f"view={view_v}")
                if vc.obl is not None:
                    obl_v = self.visit(node.obl) if node.obl not in self.vmap else self.vmap[node.obl]
                    comment_parts.append(f"obl={obl_v}")
                if comment_parts:
                    decl += " # " + ", ".join(comment_parts)
            else:
                cs = ", ".join(str(v) for v in vc)
                decl = f"{vname} = {node.__class__.__name__}{fstr}({cs})"
            self.decls.append(decl)
            self.vmap[node] = vname
        return self.vmap[node]