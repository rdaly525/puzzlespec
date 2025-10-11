from __future__ import annotations
from ..dsl import ir, ast
import typing as tp

# assumes keys have already been generated for node
def _gen_key(node: ir.Node):
    child_keys = tuple(c._key for c in node._children)
    if None in child_keys:
        from .utils import printAST
        print(child_keys)
        print(printAST(node))
    assert None not in child_keys
    fields = tuple(getattr(node, field, None) for field in node._fields)
    assert None not in fields
    priority = ir.NODE_PRIORITY[(type(node))]
    key = (priority, node.__class__.__name__, fields, child_keys)
    return key
#

def canonicalize(expr: ast.Expr) -> ast.Expr:
    canon_node = _canonicalize(expr.node)
    return ast.wrap(canon_node, expr.T)

def _canonicalize(node: ir.Node) -> ir.Node:
    if node.is_canon:
        return node
    def ass_and_com(children: tp.Iterable[ir.Node], binOp: tp.Type[ir.Node], vaOp: tp.Type[ir.Node]):
        new_children = []
        for c in children:
            if isinstance(c, (binOp, vaOp)):
                new_children += c._children
            else:
                new_children += [c]
        # Sort by keys
        return vaOp(*sorted(new_children, key=lambda c: c._key))
    new_children = [_canonicalize(c) for c in node._children]
    match (node):
        case ir.Conj() | ir.And():
            canon_node = ass_and_com(new_children, ir.And, ir.Conj)
        case ir.Disj() | ir.Or():
            canon_node = ass_and_com(new_children, ir.Or, ir.Disj)
        case ir.Prod() | ir.Mul():
            canon_node = ass_and_com(new_children, ir.Mul, ir.Prod)
        case ir.Sum() | ir.Add():
            canon_node = ass_and_com(new_children, ir.Add, ir.Sum)
        case (_):
            canon_node = node.replace(*new_children)

    if canon_node.is_canon:
        return canon_node
    canon_node._key = _gen_key(canon_node)
    return canon_node