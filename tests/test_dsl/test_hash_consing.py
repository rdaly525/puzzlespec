"""Tests for IR hash consing.

Verifies that structurally identical nodes hash/compare equal and that
differences in children, fields, named children, or _attrs are handled correctly.
"""
from puzzlespec.compiler.dsl import ir


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def int_lit(val):
    return ir.Lit(ir.IntT(), val)


def bool_lit(val):
    return ir.Lit(ir.BoolT(), val)


# ---------------------------------------------------------------------------
# Basic Value hashing
# ---------------------------------------------------------------------------

class TestValueHashConsing:
    def test_same_literal(self):
        a = int_lit(42)
        b = int_lit(42)
        assert a == b
        assert hash(a) == hash(b)

    def test_different_literal_value(self):
        a = int_lit(1)
        b = int_lit(2)
        assert a != b

    def test_different_literal_type(self):
        a = int_lit(1)
        b = bool_lit(True)
        assert a != b

    def test_same_nested(self):
        a = ir.Sum(ir.IntT(), int_lit(1), int_lit(2))
        b = ir.Sum(ir.IntT(), int_lit(1), int_lit(2))
        assert a == b
        assert hash(a) == hash(b)

    def test_different_children_order(self):
        """Sum is structurally ordered — different child order means different node."""
        a = ir.Sum(ir.IntT(), int_lit(1), int_lit(2))
        b = ir.Sum(ir.IntT(), int_lit(2), int_lit(1))
        assert a != b

    def test_different_opcode(self):
        a = ir.Sum(ir.IntT(), int_lit(1), int_lit(2))
        b = ir.Prod(ir.IntT(), int_lit(1), int_lit(2))
        assert a != b


# ---------------------------------------------------------------------------
# Type hashing
# ---------------------------------------------------------------------------

class TestTypeHashConsing:
    def test_same_base_type(self):
        a = ir.IntT()
        b = ir.IntT()
        assert a == b
        assert hash(a) == hash(b)

    def test_different_base_types(self):
        assert ir.IntT() != ir.BoolT()

    def test_same_tuple_type(self):
        a = ir.TupleT(ir.IntT(), ir.BoolT())
        b = ir.TupleT(ir.IntT(), ir.BoolT())
        assert a == b
        assert hash(a) == hash(b)

    def test_different_tuple_type_order(self):
        a = ir.TupleT(ir.IntT(), ir.BoolT())
        b = ir.TupleT(ir.BoolT(), ir.IntT())
        assert a != b

    def test_same_dom_type(self):
        a = ir.DomT(ir.IntT())
        b = ir.DomT(ir.IntT())
        assert a == b
        assert hash(a) == hash(b)

    def test_different_dom_carrier(self):
        a = ir.DomT(ir.IntT())
        b = ir.DomT(ir.BoolT())
        assert a != b

    def test_same_enum_type(self):
        a = ir.EnumT("Color", ("R", "G", "B"))
        b = ir.EnumT("Color", ("R", "G", "B"))
        assert a == b
        assert hash(a) == hash(b)

    def test_different_enum_labels(self):
        a = ir.EnumT("Color", ("R", "G", "B"))
        b = ir.EnumT("Color", ("R", "G"))
        assert a != b

    def test_different_enum_name(self):
        a = ir.EnumT("Color", ("R", "G"))
        b = ir.EnumT("Shade", ("R", "G"))
        assert a != b


# ---------------------------------------------------------------------------
# Named children on Type (ref, view, obl)
# ---------------------------------------------------------------------------

class TestTypeNamedChildren:
    def test_same_ref(self):
        ref = ir.Fin(ir.DomT(ir.IntT()), int_lit(5))
        a = ir.IntT(ref=ref)
        b = ir.IntT(ref=ref)
        assert a == b
        assert hash(a) == hash(b)

    def test_structurally_equal_ref(self):
        ref1 = ir.Fin(ir.DomT(ir.IntT()), int_lit(5))
        ref2 = ir.Fin(ir.DomT(ir.IntT()), int_lit(5))
        a = ir.IntT(ref=ref1)
        b = ir.IntT(ref=ref2)
        assert a == b
        assert hash(a) == hash(b)

    def test_different_ref(self):
        ref1 = ir.Fin(ir.DomT(ir.IntT()), int_lit(5))
        ref2 = ir.Fin(ir.DomT(ir.IntT()), int_lit(10))
        a = ir.IntT(ref=ref1)
        b = ir.IntT(ref=ref2)
        assert a != b

    def test_ref_vs_no_ref(self):
        ref = ir.Fin(ir.DomT(ir.IntT()), int_lit(5))
        a = ir.IntT(ref=ref)
        b = ir.IntT()
        assert a != b

    def test_same_obl(self):
        obl = bool_lit(True)
        a = ir.IntT(obl=obl)
        b = ir.IntT(obl=obl)
        assert a == b
        assert hash(a) == hash(b)

    def test_different_obl(self):
        a = ir.IntT(obl=bool_lit(True))
        b = ir.IntT(obl=bool_lit(False))
        assert a != b

    def test_obl_vs_no_obl(self):
        a = ir.IntT(obl=bool_lit(True))
        b = ir.IntT()
        assert a != b

    def test_same_view(self):
        view = ir.ViewT()
        a = ir.IntT(view=view)
        b = ir.IntT(view=view)
        assert a == b
        assert hash(a) == hash(b)

    def test_view_vs_no_view(self):
        a = ir.IntT(view=ir.ViewT())
        b = ir.IntT()
        assert a != b

    def test_same_ref_and_obl(self):
        ref = ir.Fin(ir.DomT(ir.IntT()), int_lit(3))
        obl = bool_lit(True)
        a = ir.IntT(ref=ref, obl=obl)
        b = ir.IntT(ref=ref, obl=obl)
        assert a == b
        assert hash(a) == hash(b)

    def test_same_ref_different_obl(self):
        ref = ir.Fin(ir.DomT(ir.IntT()), int_lit(3))
        a = ir.IntT(ref=ref, obl=bool_lit(True))
        b = ir.IntT(ref=ref, obl=bool_lit(False))
        assert a != b

    def test_different_ref_same_obl(self):
        obl = bool_lit(True)
        a = ir.IntT(ref=ir.Fin(ir.DomT(ir.IntT()), int_lit(3)), obl=obl)
        b = ir.IntT(ref=ir.Fin(ir.DomT(ir.IntT()), int_lit(5)), obl=obl)
        assert a != b


# ---------------------------------------------------------------------------
# Named children on Value (T, obl)
# ---------------------------------------------------------------------------

class TestValueNamedChildren:
    def test_same_type(self):
        a = int_lit(1)
        b = int_lit(1)
        assert a.T == b.T
        assert a == b

    def test_different_type_same_val(self):
        """Same literal value but different types should differ."""
        a = ir.Lit(ir.IntT(), 0)
        b = ir.Lit(ir.BoolT(), 0)
        assert a != b

    def test_refined_type_vs_plain(self):
        """Value with a refined type differs from one with a plain type."""
        plain_t = ir.IntT()
        ref = ir.Fin(ir.DomT(ir.IntT()), int_lit(5))
        refined_t = ir.IntT(ref=ref)
        a = ir.Lit(plain_t, 3)
        b = ir.Lit(refined_t, 3)
        assert a != b

    def test_same_obl_on_value(self):
        obl = bool_lit(True)
        a = int_lit(7)
        a_guarded = ir.Lit(ir.IntT(), 7, obl=obl)
        b_guarded = ir.Lit(ir.IntT(), 7, obl=obl)
        assert a_guarded == b_guarded
        assert hash(a_guarded) == hash(b_guarded)
        assert a != a_guarded

    def test_different_obl_on_value(self):
        a = ir.Lit(ir.IntT(), 7, obl=bool_lit(True))
        b = ir.Lit(ir.IntT(), 7, obl=bool_lit(False))
        assert a != b

    def test_obl_vs_no_obl_on_value(self):
        a = ir.Lit(ir.IntT(), 7)
        b = ir.Lit(ir.IntT(), 7, obl=bool_lit(True))
        assert a != b

    def test_nested_value_with_obl(self):
        obl = bool_lit(True)
        x = ir.Lit(ir.IntT(), 1, obl=obl)
        y = ir.Lit(ir.IntT(), 2)
        a = ir.Sum(ir.IntT(), x, y)
        b = ir.Sum(ir.IntT(), x, y)
        assert a == b
        assert hash(a) == hash(b)

    def test_nested_value_different_child_obl(self):
        """Two Sums with children that differ only in obl should differ."""
        x1 = ir.Lit(ir.IntT(), 1, obl=bool_lit(True))
        x2 = ir.Lit(ir.IntT(), 1)
        y = ir.Lit(ir.IntT(), 2)
        a = ir.Sum(ir.IntT(), x1, y)
        b = ir.Sum(ir.IntT(), x2, y)
        assert a != b


# ---------------------------------------------------------------------------
# _metadata does NOT affect hash or equality
# ---------------------------------------------------------------------------

class TestMetadataDoesNotAffectEquality:
    def test_different_metadata_still_equal(self):
        a = int_lit(42)
        b = int_lit(42)
        a._metadata["info"] = "something"
        assert a == b
        assert hash(a) == hash(b)

    def test_metadata_does_not_change_hash(self):
        a = int_lit(42)
        h_before = hash(a)
        a._metadata["extra"] = 999
        assert hash(a) == h_before

    def test_metadata_copied_on_replace(self):
        a = int_lit(42)
        a._metadata["tag"] = "original"
        b = a.replace(T=ir.IntT(), obl=None, val=99)
        assert b._metadata["tag"] == "original"
        assert b != a  # different val field


# ---------------------------------------------------------------------------
# Fields affect hash
# ---------------------------------------------------------------------------

class TestFieldsAffectHash:
    def test_same_fields(self):
        a = ir.BoundVar(ir.IntT(), idx=0)
        b = ir.BoundVar(ir.IntT(), idx=0)
        assert a == b
        assert hash(a) == hash(b)

    def test_different_fields(self):
        a = ir.BoundVar(ir.IntT(), idx=0)
        b = ir.BoundVar(ir.IntT(), idx=1)
        assert a != b


# ---------------------------------------------------------------------------
# Dict/set usability (hash consing in practice)
# ---------------------------------------------------------------------------

class TestHashConsingInCollections:
    def test_set_deduplication(self):
        nodes = {int_lit(1), int_lit(1), int_lit(2), int_lit(2), int_lit(3)}
        assert len(nodes) == 3

    def test_dict_lookup(self):
        d = {}
        key = ir.Sum(ir.IntT(), int_lit(1), int_lit(2))
        d[key] = "found"
        lookup = ir.Sum(ir.IntT(), int_lit(1), int_lit(2))
        assert d[lookup] == "found"

    def test_set_distinguishes_named_children(self):
        """Nodes differing only in named children should be distinct in a set."""
        plain = ir.IntT()
        refined = ir.IntT(ref=ir.Fin(ir.DomT(ir.IntT()), int_lit(5)))
        nodes = {plain, refined}
        assert len(nodes) == 2

    def test_dict_lookup_with_obl(self):
        d = {}
        k1 = ir.Lit(ir.IntT(), 1, obl=bool_lit(True))
        d[k1] = "guarded"
        k2 = ir.Lit(ir.IntT(), 1, obl=bool_lit(True))
        assert d[k2] == "guarded"
        k3 = ir.Lit(ir.IntT(), 1)
        assert k3 not in d
