from __future__ import annotations

import typing as tp

from ..pass_base import Transform, Context, handles, AnalysisObject
from ...dsl import ir, ast
from ....libs import var_def, std

#def guard_opt(node: ir.Node):
#    assert isinstance(node, ir.Node)
#    node = GuardOpt()(node, Context())[0]
#    return node

def _has_bv(node: ir.Node, name: str):
    if isinstance(node, ir.BoundVarHOAS) and node.name==name:
        return True
    return any(_has_bv(c, name) for c in node._children)

def _get_bvs(node: ir.Node):
    if isinstance(node, ir.BoundVarHOAS):
        return {node.name}
    ret = set()
    if isinstance(node, (ir.LambdaHOAS, ir.PiTHOAS)):
        T, body = node._children
        ret |= _get_bvs(T)
        body_bvs = _get_bvs(body)
        ret |= (body_bvs - {node.bv_name})
    else:
        for c in node._children:
            ret |= _get_bvs(c)
    return ret

# The goal is to lift up guards from child nodes to parent nodes
class GuardStrip(Transform):
    """ Removes all guards. Useful for printing
    """
    name = "guard_strip"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        new_root = self.visit(root)
        return new_root

    @handles(ir.Guard)
    def _(self, node: ir.Node):
        T, val, pre = self.visit_children(node)
        return val

    @handles(ir.GuardT)
    def _(self, node: ir.Node):
        T, pre = self.visit_children(node)
        return T

# The goal is to lift up guards from child nodes to parent nodes
class GuardLift(Transform):
    """ Lifts top level guards
    """
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
            for c in pre._children[1:]:
                self.preds.add(c)
        else:
            self.preds.add(pre)
    
    @handles(ir.Guard)
    def _(self, node: ir.Guard):
        T, new_val, pre = self.visit_children(node)
        self.handle_pre(pre)
        return new_val

    @handles(ir.GuardT)
    def _(self, node: ir.GuardT):
        T, pre = self.visit_children(node)
        self.handle_pre(pre)
        return T

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
        T, body = node._children
        newT = self.visit(T)
        cur_preds = self.preds
        self.preds = set()
        new_body = self.visit(body)
        dep_preds, ndep_preds = self.filter_preds(node.bv_name)
        self.preds = cur_preds | ndep_preds
        if len(dep_preds)>0:
            new_body = ast.wrap(new_body).guard(std.all(ast.wrap(p) for p in dep_preds)).node
        return node.replace(newT, new_body)

    @handles(ir.PiTHOAS)
    def _(self, node: ir.PiTHOAS):
        argT, resT = node._children
        new_argT = self.visit(argT)
        cur_preds = self.preds
        self.preds = set()
        new_resT = self.visit(resT)
        dep_preds, ndep_preds = self.filter_preds(node.bv_name)
        self.preds = cur_preds | ndep_preds
        if len(dep_preds)>0:
            new_resT = ast.wrapT(new_resT).guard(std.all(ast.wrap(p) for p in dep_preds)).node
        return node.replace(new_argT, new_resT)

    @handles(ir.Spec)
    def _(self, node: ir.Spec):
        cons, obs = self.visit_children(node)
        assert not isinstance(obs, ir.Guard)
        if isinstance(cons, ir.Guard):
            T, cons, p = cons._children
            obs = ast.TupleExpr.make((ast.wrap(p),)).node
            return ir.Spec(
                cons,
                obs
            )
        return node.replace(cons, obs)

class GuardOpt(Transform):
    """ guard opt
    """
    name = "guard_opt"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        return self.visit(root)

    @handles(ir.GuardT)
    def _(self, node: ir.GuardT):
        T, pred = self.visit_children(node)
        if pred == std.true.node:
            return T
        return node.replace(T, pred)

    @handles(ir.Guard)
    def _(self, node: ir.Guard):
        T, v, pred = self.visit_children(node)
        if pred == std.true.node:
            return v
        return node.replace(T, v, pred)


# The goal is to lift up guards from child nodes to parent nodes
class _GuardOpt(Transform):
    """ guard opt
    """
    name = "guard_opt"

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        self.preds = {}
        new_root = self.visit(root)
        return new_root

    def _simp_child_guards(self, node: ir.Node):
        children = self.visit_children(node)
        ps = []
        new_children = []
        for c in children:
            if isinstance(c, ir.GuardT):
                c, p = c._children
                if isinstance(p, ir.Conj):
                    ps.extend(p._children[1:])
                else:
                    ps.append(p)
            elif isinstance(c, ir.Guard):
                _, c, p = c._children
                if isinstance(p, ir.Conj):
                    ps.extend(p._children[1:])
                else:
                    ps.append(p)               
            new_children.append(c)
        if len(ps)==0:
            return node.replace(*children), []
        return node.replace(*new_children), [ast.wrap(p) for p in ps]

    def visit(self, node: ir.Node):
        new_node, ps = self._simp_child_guards(node)
        if len(ps) == 0:
            return new_node
        if isinstance(new_node, ir.Value):
            node = ast.wrap(new_node).guard(std.all(ps)).node
        else:
            node = ast.wrapT(new_node).guard(std.all(ps)).node
        return node
            
    @handles(ir.PiTHOAS)
    def _(self, node: ir.PiTHOAS):
        argT, resT = node._children
        argT, psA = self._simp_child_guards(argT)
        resT, psR = self._simp_child_guards(resT)
        # sort psR into depednent and non
        ps = psA
        dep_ps = []
        for p in psR:
            if _has_bv(p.node, node.bv_name):
                dep_ps.append(p)
            else:
                ps.append(p)
        if len(dep_ps)>0:
            argT = ast.wrapT(argT).guard(std.all(dep_ps)).node
        new_node = node.replace(argT, resT)
        if len(ps) == 0:
            return new_node
        return ast.wrapT(new_node).guard(std.all(ps)).node

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        T, body = node._children
        T, psT = self._simp_child_guards(T)
        body, psB = self._simp_child_guards(body)
        # sort psB into depednent and non
        ps = psT
        dep_ps = []
        for p in psB:
            if _has_bv(p.node, node.bv_name):
                dep_ps.append(p)
            else:
                ps.append(p)
        if len(dep_ps)>0:
            body = ast.wrap(body).guard(std.all(dep_ps)).node
        new_node = node.replace(T, body)
        if len(ps) == 0:
            return new_node
        return ast.wrap(new_node).guard(std.all(ps)).node

    @handles(ir.GuardT)
    def _(self, node: ir.GuardT):
        node, ps = self._simp_child_guards(node)
        T, pre = node._children
        if len(ps) == 0:
            match pre:
                case ir.Lit(_, val=True):
                    return T
            return node
        ps.append(pre)
        return ast.wrapT(T).guard(std.all(ps)).node

    @handles(ir.Guard)
    def _(self, node: ir.Guard):
        node, ps = self._simp_child_guards(node)
        T, new_val, pre = node._children
        if len(ps) ==0:
            match pre:
                case ir.Lit(_, val=True):
                    return new_val
            return node
        ps.append(pre)
        return ast.wrap(new_val).guard(std.all(ps)).node

    @handles(ir.Spec)
    def _(self, node: ir.Spec):
        cons, obs = self.visit_children(node)
        assert not isinstance(obs, ir.Guard)
        if isinstance(cons, ir.Guard):
            T, cons, p = cons._children
            obs = ast.TupleExpr.make((ast.wrap(p),)).node
            return ir.Spec(
                cons,
                obs
            )
        return node.replace(cons, obs)