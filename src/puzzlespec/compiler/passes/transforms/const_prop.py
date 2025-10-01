from __future__ import annotations

from ..pass_base import Transform, Context, handles
from ...dsl import ir
import typing as tp


def _is_lit(node: ir.Node) -> tp.Tuple[bool, tp.Any]:
    if isinstance(node, ir.Lit):
        return True, node.value
    return False, None


class ConstPropPass(Transform):
    """Constant propagation and simple algebraic/boolean simplifications.

    - Folds arithmetic and boolean ops when operands are literals
    - Applies simple identities (e.g., And/Or short-circuit with literals,
      Add 0, Mul 1/0, etc.)
    - Simplifies structural lengths (ListLength, DictLength) when operands are
      literal structures
    - Evaluates comparisons and equality on literals

    Leaves non-constant structures intact.
    """

    requires: tp.Tuple[type, ...] = ()
    produces: tp.Tuple[type, ...] = ()
    name = "const_prop"

    # Arithmetic
    @handles(ir.Add)
    def _(self, node: ir.Add) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        a_is, av = _is_lit(a)
        b_is, bv = _is_lit(b)
        if a_is and b_is:
            return ir.Lit(av + bv)
        # Identities
        if a_is and av == 0:
            return b
        if b_is and bv == 0:
            return a
        return node if (a is node._children[0] and b is node._children[1]) else ir.Add(a, b)

    @handles(ir.Sub)
    def _(self, node: ir.Sub) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        a_is, av = _is_lit(a)
        b_is, bv = _is_lit(b)
        if a_is and b_is:
            return ir.Lit(av - bv)
        if b_is and bv == 0:
            return a
        return node if (a is node._children[0] and b is node._children[1]) else ir.Sub(a, b)

    @handles(ir.Mul)
    def _(self, node: ir.Mul) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        a_is, av = _is_lit(a)
        b_is, bv = _is_lit(b)
        if a_is and b_is:
            return ir.Lit(av * bv)
        # Identities
        if a_is and av == 0:
            return ir.Lit(0)
        if b_is and bv == 0:
            return ir.Lit(0)
        if a_is and av == 1:
            return b
        if b_is and bv == 1:
            return a
        return node if (a is node._children[0] and b is node._children[1]) else ir.Mul(a, b)

    @handles(ir.Div)
    def _(self, node: ir.Div) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        a_is, av = _is_lit(a)
        b_is, bv = _is_lit(b)
        if b_is and bv == 0:
            # Avoid folding division by zero
            return node if (a is node._children[0] and b is node._children[1]) else ir.Div(a, b)
        if a_is and b_is:
            return ir.Lit(av // bv)
        if b_is and bv == 1:
            return a
        return node if (a is node._children[0] and b is node._children[1]) else ir.Div(a, b)

    @handles(ir.Mod)
    def _(self, node: ir.Mod) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        a_is, av = _is_lit(a)
        b_is, bv = _is_lit(b)
        if b_is and bv == 0:
            # Leave modulo by zero unchanged
            return node if (a is node._children[0] and b is node._children[1]) else ir.Mod(a, b)
        if a_is and b_is:
            return ir.Lit(av % bv)
        if b_is and bv == 1:
            return ir.Lit(0)
        return node if (a is node._children[0] and b is node._children[1]) else ir.Mod(a, b)

    # Comparisons
    @handles(ir.Gt)
    def _(self, node: ir.Gt) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        a_is, av = _is_lit(a)
        b_is, bv = _is_lit(b)
        if a_is and b_is:
            return ir.Lit(av > bv)
        return node if (a is node._children[0] and b is node._children[1]) else ir.Gt(a, b)

    @handles(ir.GtEq)
    def _(self, node: ir.GtEq) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        a_is, av = _is_lit(a)
        b_is, bv = _is_lit(b)
        if a_is and b_is:
            return ir.Lit(av >= bv)
        return node if (a is node._children[0] and b is node._children[1]) else ir.GtEq(a, b)

    @handles(ir.Lt)
    def _(self, node: ir.Lt) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        a_is, av = _is_lit(a)
        b_is, bv = _is_lit(b)
        if a_is and b_is:
            return ir.Lit(av < bv)
        return node if (a is node._children[0] and b is node._children[1]) else ir.Lt(a, b)

    @handles(ir.LtEq)
    def _(self, node: ir.LtEq) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        a_is, av = _is_lit(a)
        b_is, bv = _is_lit(b)
        if a_is and b_is:
            return ir.Lit(av <= bv)
        return node if (a is node._children[0] and b is node._children[1]) else ir.LtEq(a, b)

    @handles(ir.Eq)
    def _(self, node: ir.Eq) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        a_is, av = _is_lit(a)
        b_is, bv = _is_lit(b)
        if a_is and b_is:
            return ir.Lit(av == bv)
        # x == x => True (only if structurally the same node reference after visiting)
        if a is b:
            return ir.Lit(True)
        return node if (a is node._children[0] and b is node._children[1]) else ir.Eq(a, b)

    # Booleans
    @handles(ir.Not)
    def _(self, node: ir.Not) -> ir.Node:
        a = self.visit(node._children[0])
        a_is, av = _is_lit(a)
        if a_is:
            return ir.Lit(not av)
        return node if (a is node._children[0]) else ir.Not(a)

    @handles(ir.And)
    def _(self, node: ir.And) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        a_is, av = _is_lit(a)
        b_is, bv = _is_lit(b)
        if a_is and b_is:
            return ir.Lit(av and bv)
        if a_is:
            return b if av else ir.Lit(False)
        if b_is:
            return a if bv else ir.Lit(False)
        return node if (a is node._children[0] and b is node._children[1]) else ir.And(a, b)

    @handles(ir.Or)
    def _(self, node: ir.Or) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        a_is, av = _is_lit(a)
        b_is, bv = _is_lit(b)
        if a_is and b_is:
            return ir.Lit(av or bv)
        if a_is:
            return ir.Lit(True) if av else b
        if b_is:
            return ir.Lit(True) if bv else a
        return node if (a is node._children[0] and b is node._children[1]) else ir.Or(a, b)

    @handles(ir.Implies)
    def _(self, node: ir.Implies) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        a_is, av = _is_lit(a)
        b_is, bv = _is_lit(b)
        if a_is and b_is:
            return ir.Lit((not av) or bv)
        if a_is:
            return b if av else ir.Lit(True)
        if b_is:
            return ir.Lit(True) if bv else self._make_not(a)
        return node if (a is node._children[0] and b is node._children[1]) else ir.Implies(a, b)

    def _make_not(self, n: ir.Node) -> ir.Node:
        # Avoid double negation on literal path; caller ensures n already simplified
        is_l, v = _is_lit(n)
        if is_l:
            return ir.Lit(not v)
        return ir.Not(n)

    # Variadic boolean simplifications
    @handles(ir.Conj)
    def _(self, node: ir.Conj) -> ir.Node:
        # Visit and flatten nested Conj; short-circuit on False; drop True
        new_children = []
        changed = False
        for ch in node._children:
            v = self.visit(ch)
            if v is not ch:
                changed = True
            # Flatten
            if isinstance(v, ir.Conj):
                new_children.extend(v._children)
                changed = True
                continue
            is_l, val = _is_lit(v)
            if is_l:
                if val is False:
                    return ir.Lit(False)
                # skip True
                if val is True:
                    changed = True
                    continue
            new_children.append(v)
        # Neutral/degenerate cases
        if len(new_children) == 0:
            return ir.Lit(True)
        if len(new_children) == 1:
            return new_children[0]
        return node if not changed else ir.Conj(*new_children)

    @handles(ir.Disj)
    def _(self, node: ir.Disj) -> ir.Node:
        # Visit and flatten nested Disj; short-circuit on True; drop False
        new_children = []
        changed = False
        for ch in node._children:
            v = self.visit(ch)
            if v is not ch:
                changed = True
            if isinstance(v, ir.Disj):
                new_children.extend(v._children)
                changed = True
                continue
            is_l, val = _is_lit(v)
            if is_l:
                if val is True:
                    return ir.Lit(True)
                if val is False:
                    changed = True
                    continue
            new_children.append(v)
        if len(new_children) == 0:
            return ir.Lit(False)
        if len(new_children) == 1:
            return new_children[0]
        return node if not changed else ir.Disj(*new_children)

    # Structural / collections
    @handles(ir.ListLength)
    def _(self, node: ir.ListLength) -> ir.Node:
        lst = self.visit(node._children[0])
        if isinstance(lst, ir.List):
            # child 0 is a node that stores the list length (typically Lit)
            return lst._children[0]
        return node if (lst is node._children[0]) else ir.ListLength(lst)

    @handles(ir.DictLength)
    def _(self, node: ir.DictLength) -> ir.Node:
        d = self.visit(node._children[0])
        if isinstance(d, ir.Dict):
            # number of key/value pairs
            num_pairs = len(d._children) // 2
            return ir.Lit(num_pairs)
        return node if (d is node._children[0]) else ir.DictLength(d)

    @handles(ir.ListGet)
    def _(self, node: ir.ListGet) -> ir.Node:
        lst = self.visit(node._children[0])
        idx = self.visit(node._children[1])
        idx_is, iv = _is_lit(idx)
        if isinstance(lst, ir.List) and idx_is and isinstance(iv, int):
            # children: (length, e0, e1, ...)
            elems = lst._children[1:]
            if 0 <= iv < len(elems):
                return elems[iv]
        return node if (lst is node._children[0] and idx is node._children[1]) else ir.ListGet(lst, idx)

    @handles(ir.ListConcat)
    def _(self, node: ir.ListConcat) -> ir.Node:
        a = self.visit(node._children[0])
        b = self.visit(node._children[1])
        if isinstance(a, ir.List) and isinstance(b, ir.List):
            len_a_node = a._children[0]
            len_b_node = b._children[0]
            len_a_is, len_a = _is_lit(len_a_node)
            len_b_is, len_b = _is_lit(len_b_node)
            if len_a_is and len_b_is:
                new_len = ir.Lit(len_a + len_b)
            else:
                # fallback: recompute from element counts
                new_len = ir.Lit(len(a._children[1:]) + len(b._children[1:]))
            new_elems = a._children[1:] + b._children[1:]
            return ir.List(new_len, *new_elems)
        return node if (a is node._children[0] and b is node._children[1]) else ir.ListConcat(a, b)

    @handles(ir.Sum)
    def _(self, node: ir.Sum) -> ir.Node:
        vals = self.visit(node._children[0])
        if isinstance(vals, ir.List):
            # Sum all literal ints if possible
            total = 0
            for e in vals._children[1:]:
                is_l, v = _is_lit(e)
                if not is_l or not isinstance(v, int):
                    break
                total += v
            else:
                return ir.Lit(total)
        return node if (vals is node._children[0]) else ir.Sum(vals)

    @handles(ir.Distinct)
    def _(self, node: ir.Distinct) -> ir.Node:
        vals = self.visit(node._children[0])
        if isinstance(vals, ir.List):
            lit_vals: tp.List[tp.Any] = []
            for e in vals._children[1:]:
                is_l, v = _is_lit(e)
                if not is_l:
                    break
                lit_vals.append(v)
            else:
                # All literals
                return ir.Lit(len(set(lit_vals)) == len(lit_vals))
        return node if (vals is node._children[0]) else ir.Distinct(vals)

    @handles(ir.GridNumRows)
    def _(self, node: ir.GridNumRows) -> ir.Node:
        g = self.visit(node._children[0])
        if isinstance(g, ir.Grid):
            return ir.Lit(g.nR)
        return node if (g is node._children[0]) else ir.GridNumRows(g)

    @handles(ir.GridNumCols)
    def _(self, node: ir.GridNumCols) -> ir.Node:
        g = self.visit(node._children[0])
        if isinstance(g, ir.Grid):
            return ir.Lit(g.nC)
        return node if (g is node._children[0]) else ir.GridNumCols(g)
