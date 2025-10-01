from __future__ import annotations

import typing as tp

from ..pass_base import Transform, handles
from ...dsl import ir
from .const_prop import ConstPropPass


def _subst_multi(node: ir.Node, mapping: tp.Dict[ir.Node, ir.Node]) -> ir.Node:
    """Clone `node`, replacing any child that is identical to a key in mapping.

    Keys should typically be `ir.BoundVar` instances (or any sub-nodes of the
    lambda parameter).
    """
    if node in mapping:
        return mapping[node]
    new_children = tuple(_subst_multi(ch, mapping) for ch in node._children)
    if new_children == node._children:
        return node
    return node.replace(*new_children)


class ConcretizeCollectionsPass(Transform):
    """Concretize collection-producing nodes when possible.

    Examples:
    - Map(List(...), Lambda) => List(...)
    - ListTabulate(Lit n, Lambda) => List(...)
    """

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "concretize_collections"

    def __init__(self) -> None:
        super().__init__()
        self._const = ConstPropPass()

    @handles(ir.Map)
    def _(self, node: ir.Map) -> ir.Node:
        domain = self.visit(node._children[0])
        fun = self.visit(node._children[1])

        # Case 1: domain is a concrete list
        if isinstance(domain, ir.List) and isinstance(fun, ir.Lambda):
            param = fun._children[0]
            body = fun._children[1]
            elems: tp.List[ir.Node] = []
            for e in domain._children[1:]:
                mapping: tp.Dict[ir.Node, ir.Node]
                if isinstance(param, ir.BoundVar):
                    mapping = {param: e}
                else:
                    # Unsupported parameter form for list map; fallback
                    mapping = {}
                applied = _subst_multi(body, mapping) if mapping else body
                simplified = self._const.visit(applied)
                elems.append(simplified)
            length = ir.Lit(len(elems))
            return ir.List(length, *elems)

        # Otherwise, rebuild if any child changed
        return node if (domain is node._children[0] and fun is node._children[1]) else ir.Map(domain, fun)

    @handles(ir.ListTabulate)
    def _(self, node: ir.ListTabulate) -> ir.Node:
        size = self.visit(node._children[0])
        fun = self.visit(node._children[1])
        # size must be a literal int and fun a lambda over Int
        if isinstance(size, ir.Lit) and isinstance(size.value, int) and isinstance(fun, ir.Lambda):
            n = size.value
            if n < 0:
                # Leave negative sizes untouched
                return node if (size is node._children[0] and fun is node._children[1]) else ir.ListTabulate(size, fun)
            param = fun._children[0]
            body = fun._children[1]
            elems: tp.List[ir.Node] = []
            for i in range(n):
                mapping: tp.Dict[ir.Node, ir.Node]
                if isinstance(param, ir.BoundVar):
                    mapping = {param: ir.Lit(i)}
                else:
                    mapping = {}
                applied = _subst_multi(body, mapping) if mapping else body
                simplified = self._const.visit(applied)
                elems.append(simplified)
            return ir.List(ir.Lit(n), *elems)
        return node if (size is node._children[0] and fun is node._children[1]) else ir.ListTabulate(size, fun)

    @handles(ir.ListWindow)
    def _(self, node: ir.ListWindow) -> ir.Node:
        lst = self.visit(node._children[0])
        size = self.visit(node._children[1])
        stride = self.visit(node._children[2])
        if isinstance(lst, ir.List) and isinstance(size, ir.Lit) and isinstance(size.value, int) and isinstance(stride, ir.Lit) and isinstance(stride.value, int):
            n = len(lst._children[1:])
            w = size.value
            s = stride.value
            if w <= 0 or s <= 0:
                return node if (lst is node._children[0] and size is node._children[1] and stride is node._children[2]) else ir.ListWindow(lst, size, stride)
            windows: tp.List[ir.Node] = []
            for start in range(0, max(0, n - w + 1), s):
                elems = lst._children[1:][start:start + w]
                windows.append(ir.List(ir.Lit(len(elems)), *elems))
            return ir.List(ir.Lit(len(windows)), *windows)
        return node if (lst is node._children[0] and size is node._children[1] and stride is node._children[2]) else ir.ListWindow(lst, size, stride)

    @handles(ir.DictTabulate)
    def _(self, node: ir.DictTabulate) -> ir.Node:
        keys = self.visit(node._children[0])
        fun = self.visit(node._children[1])
        if isinstance(keys, ir.List) and isinstance(fun, ir.Lambda):
            param = fun._children[0]
            body = fun._children[1]
            flat: tp.List[ir.Node] = []
            for k in keys._children[1:]:
                if isinstance(param, ir.BoundVar):
                    applied = _subst_multi(body, {param: k})
                else:
                    applied = body
                v = self._const.visit(applied)
                flat.extend([k, v])
            return ir.Dict(*flat)
        return node if (keys is node._children[0] and fun is node._children[1]) else ir.DictTabulate(keys, fun)

    @handles(ir.DictGet)
    def _(self, node: ir.DictGet) -> ir.Node:
        d = self.visit(node._children[0])
        k = self.visit(node._children[1])
        if isinstance(d, ir.Dict):
            keys = d._children[::2]
            vals = d._children[1::2]
            for dk, dv in zip(keys, vals):
                # match by identity or literal equality
                if k is dk:
                    return dv
                if isinstance(k, ir.Lit) and isinstance(dk, ir.Lit) and k.value == dk.value:
                    return dv
        return node if (d is node._children[0] and k is node._children[1]) else ir.DictGet(d, k)

    @handles(ir.DictMap)
    def _(self, node: ir.DictMap) -> ir.Node:
        d = self.visit(node._children[0])
        fun = self.visit(node._children[1])
        if isinstance(d, ir.Dict) and isinstance(fun, ir.Lambda):
            param = fun._children[0]
            body = fun._children[1]
            flat: tp.List[ir.Node] = []
            keys = d._children[::2]
            vals = d._children[1::2]
            for k, v in zip(keys, vals):
                mapping: tp.Dict[ir.Node, ir.Node] = {}
                if isinstance(param, ir.BoundVar):
                    mapping = {param: ir.Tuple(k, v)}
                elif isinstance(param, ir.Tuple) and len(param._children) == 2:
                    a, b = param._children
                    if isinstance(a, ir.BoundVar) and isinstance(b, ir.BoundVar):
                        mapping = {a: k, b: v}
                applied = _subst_multi(body, mapping) if mapping else body
                new_v = self._const.visit(applied)
                flat.extend([k, new_v])
            return ir.Dict(*flat)
        return node if (d is node._children[0] and fun is node._children[1]) else ir.DictMap(d, fun)

    @handles(ir.Forall)
    def _(self, node: ir.Forall) -> ir.Node:
        domain = self.visit(node._children[0])
        fun = self.visit(node._children[1])
        if not isinstance(fun, ir.Lambda):
            return node if (domain is node._children[0] and fun is node._children[1]) else ir.Forall(domain, fun)
        param = fun._children[0]
        body = fun._children[1]
        # For lists: iterate elements; for dicts: iterate key/value pairs
        if isinstance(domain, ir.List):
            elems = domain._children[1:]
            # Vacuous truth for empty list
            result: ir.Node = ir.Lit(True)
            for e in elems:
                mapping = {param: e} if isinstance(param, ir.BoundVar) else {}
                cond = self._const.visit(_subst_multi(body, mapping) if mapping else body)
                result = self._const.visit(ir.And(result, cond))
            return result
        elif isinstance(domain, ir.Dict):
            keys = domain._children[::2]
            vals = domain._children[1::2]
            result: ir.Node = ir.Lit(True)
            for k, v in zip(keys, vals):
                mapping: tp.Dict[ir.Node, ir.Node] = {}
                if isinstance(param, ir.BoundVar):
                    mapping = {param: ir.Tuple(k, v)}
                elif isinstance(param, ir.Tuple) and len(param._children) == 2:
                    a, b = param._children
                    if isinstance(a, ir.BoundVar) and isinstance(b, ir.BoundVar):
                        mapping = {a: k, b: v}
                cond = self._const.visit(_subst_multi(body, mapping) if mapping else body)
                result = self._const.visit(ir.And(result, cond))
            return result
        return node if (domain is node._children[0] and fun is node._children[1]) else ir.Forall(domain, fun)

    # Normalize nested binary And/Or into variadic Conj/Disj for downstream passes
    @handles(ir.And)
    def _(self, node: ir.And) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        flat: tp.List[ir.Node] = []
        def push(v: ir.Node):
            if isinstance(v, ir.Conj):
                flat.extend(v._children)
            elif isinstance(v, ir.And):
                # In case recursive binary survived, expand
                push(v._children[0])
                push(v._children[1])
            else:
                flat.append(v)
        push(a); push(b)
        return ir.Conj(*flat)

    @handles(ir.Or)
    def _(self, node: ir.Or) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        flat: tp.List[ir.Node] = []
        def push(v: ir.Node):
            if isinstance(v, ir.Disj):
                flat.extend(v._children)
            elif isinstance(v, ir.Or):
                push(v._children[0])
                push(v._children[1])
            else:
                flat.append(v)
        push(a); push(b)
        return ir.Disj(*flat)


