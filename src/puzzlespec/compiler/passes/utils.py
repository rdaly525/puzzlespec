from ..dsl import ir, ast, ir_types as irT
from .pass_base import PassManager
from .transforms import ConstFoldPass, AlgebraicSimplificationPass
# Context Free optimization (i.e., no need for environments)


def printAST(node: ir.Node, l=0):
    field_str = ",".join([f"{k}={v}" for k,v in node.field_dict.items()])
    if field_str:
        field_str = f"[{field_str}]"
    indent = "|   "*l
    child_strs = "".join([printAST(c, l+1) for c in node._children])
    return f"{indent}{node.__class__.__name__}{field_str}: {id(node)%255}\n{child_strs}"
 
