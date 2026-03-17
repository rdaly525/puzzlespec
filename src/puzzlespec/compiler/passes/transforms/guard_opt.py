from __future__ import annotations

import typing as tp

from ..pass_base import Transform, Context, handles, AnalysisObject
from ...dsl import ir, ast
from ....libs import var_def, std


def _has_bv(node: ir.Node, name: str):
    if isinstance(node, ir.BoundVarHOAS) and node.name == name:
        return True
    return any(_has_bv(c, name) for c in node.all_nodes)

def _get_bvs(node: ir.Node):
    if isinstance(node, ir.BoundVarHOAS):
        return {node.name}
    ret = set()
    if isinstance(node, (ir.LambdaHOAS, ir.PiTHOAS)):
        body = node._children[0] if isinstance(node, ir.LambdaHOAS) else node._children[1]
        for c in node.all_nodes:
            ret |= _get_bvs(c)
        ret -= {node.bv_name}
    else:
        for c in node.all_nodes:
            ret |= _get_bvs(c)
    return ret


class GuardStrip(Transform):
    """Removes all obligations from Value and Type nodes."""
    name = "guard_strip"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        return self.visit(root)

    def visit(self, node: ir.Node) -> ir.Node:
        if isinstance(node, ir.Value):
            vc = self.visit_children(node)
            return node.replace(*vc.children, T=vc.T, obl=None)
        elif isinstance(node, ir.Type):
            vc = self.visit_children(node)
            return node.replace(*vc.children, ref=vc.ref, view=vc.view, obl=None)
        else:
            new_children = self.visit_children(node)
            return node.replace(*new_children)


class GuardLift(Transform):
    """Lifts top-level obligations out of the tree into collected predicates."""
    name = "guard_lift"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        self.bstack = []
        self.preds = set()
        new_root = self.visit(root)
        if len(self.preds) > 0:
            new_root = ast.wrap(new_root).guard(std.all(ast.wrap(p) for p in self.preds)).node
        return new_root

    def handle_pre(self, pre: ir.Node):
        if isinstance(pre, ir.Conj):
            for c in pre._children:
                self.preds.add(c)
        else:
            self.preds.add(pre)

    def visit(self, node: ir.Node) -> ir.Node:
        if isinstance(node, ir.Value):
            vc = self.visit_children(node)
            if vc.obl is not None:
                self.handle_pre(vc.obl)
            return node.replace(*vc.children, T=vc.T, obl=None)
        elif isinstance(node, ir.Type):
            vc = self.visit_children(node)
            if vc.obl is not None:
                self.handle_pre(vc.obl)
            return node.replace(*vc.children, ref=vc.ref, view=vc.view, obl=None)
        else:
            new_children = self.visit_children(node)
            return node.replace(*new_children)

    def filter_preds(self, bv_name: str):
        dep_preds = set()
        ndep_preds = set()
        for p in self.preds:
            if _has_bv(p, bv_name):
                dep_preds.add(p)
            else:
                ndep_preds.add(p)
        return dep_preds, ndep_preds

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        body = node._children[0]
        newT = self.visit(node.T)
        cur_preds = self.preds
        self.preds = set()
        new_body = self.visit(body)
        dep_preds, ndep_preds = self.filter_preds(node.bv_name)
        self.preds = cur_preds | ndep_preds
        new_obl = None
        if len(dep_preds) > 0:
            new_body = ast.wrap(new_body).guard(std.all(ast.wrap(p) for p in dep_preds)).node
        return node.replace(new_body, T=newT, obl=None)

    @handles(ir.PiTHOAS)
    def _(self, node: ir.PiTHOAS):
        argT, resT = node._children
        new_argT = self.visit(argT)
        cur_preds = self.preds
        self.preds = set()
        new_resT = self.visit(resT)
        dep_preds, ndep_preds = self.filter_preds(node.bv_name)
        self.preds = cur_preds | ndep_preds
        if len(dep_preds) > 0:
            new_resT = ast.wrapT(new_resT).guard(std.all(ast.wrap(p) for p in dep_preds)).node
        return node.replace(new_argT, new_resT, ref=node.ref, view=node.view, obl=None)

    @handles(ir.Spec)
    def _(self, node: ir.Spec):
        cons, obs = self.visit_children(node)
        if cons.obl is not None:
            p = cons.obl
            cons = cons.replace(*cons._children, T=cons.T, obl=None)
            obs = ast.TupleExpr.make((ast.wrap(p),)).node
            return ir.Spec(cons, obs)
        return node.replace(cons, obs)


class GuardOpt(Transform):
    """Removes trivially-true obligations."""
    name = "guard_opt"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        return self.visit(root)

    def visit(self, node: ir.Node) -> ir.Node:
        if isinstance(node, ir.Value):
            vc = self.visit_children(node)
            obl = vc.obl
            if obl is not None and obl == std.true.node:
                obl = None
            return node.replace(*vc.children, T=vc.T, obl=obl)
        elif isinstance(node, ir.Type):
            vc = self.visit_children(node)
            obl = vc.obl
            if obl is not None and obl == std.true.node:
                obl = None
            return node.replace(*vc.children, ref=vc.ref, view=vc.view, obl=obl)
        else:
            new_children = self.visit_children(node)
            return node.replace(*new_children)
