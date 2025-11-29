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
    requires = () #(EnvsObj,)
    produces = (PrintedAST,)
    name = "ast_printer"
    enable_memoization=False

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        #self.tenv = ctx.get(EnvsObj).tenv
        self.bctx = []
        self.depth = 0
        rendered = self.visit(root)
        print("AST")
        print("*"*80)
        print(rendered)
        print("*"*80)
        return PrintedAST(rendered)
    
    def _new_elem_name(self) -> str:
        # count existing element binders in the env
        k = sum(1 for n in self.b_names if n.startswith("x"))
        return f"x{k}"

    def _new_col_name(self) -> str:
        k = sum(1 for n in self.b_names if n.startswith("X"))
        return f"X{k}"
    
    def visit(self, node: ir.Node):
        self.depth += 1
        children_strs = self.visit_children(node)
        fstr = ", ".join([f"{k}={v}" for k,v in node.field_dict.items()])
        if fstr:
            fstr = f"[{fstr}]"
        indent = "|  "*self.depth
        node_prefix = indent + f"{node.__class__.__name__}{fstr}: {str(id(node))[-5:]}"
        if node.num_children > 0:
            s = node_prefix + "(\n" + "\n".join(cs for cs in children_strs) + f"\n{indent})"
        else:
            s = node_prefix + "()"
         #if len(children_strs)==0:
        #    print(type(node))
        #    assert 0
        self.depth -= 1
        return s
 
    #def value_str(self, node: ir.Node, T_str, children_strs) -> str:
   
    #@handles(ir.BoolT, ir.IntT, ir.UnitT, ir.ArrowT, ir.DomT, ir.SumT, ir.TupleT, ir.EnumT, ir.FuncT)
    #def _(self, T: ir.Node):
    #    return str(T)

    #@handles(ir.BoundVar)
    #def _(self, node: ir.BoundVar):
    #    T_str = self.bctx[-(node.idx+1)]
    #    return self.value_str(node, T_str, ())

    #@handles(ir.Lambda)
    #def _(self, node: ir.Lambda):
    #    T, body = node._children
    #    T_str = self.visit(T)
    #    self.depth +=1
    #    self.bctx.append(T_str)
    #    body_str = self.visit(body)
    #    self.bctx.pop()
    #    self.depth-=1
    #    return self.value_str(node, T_str, (body_str,))

    #@handles(ir.VarRef)
    #def _(self, node: ir.VarRef):
    #    return "|  "*self.depth + f"X{node.sid}: " + str(self.tenv[node.sid])
    