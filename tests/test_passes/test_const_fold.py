"""ConstFoldPass: fold nodes whose children are all literals."""
from puzzlespec import Int
from puzzlespec.compiler.dsl import ir, ast
from puzzlespec.compiler.passes.transforms.const_fold import ConstFoldPass
from .conftest import run_transform


def test_sum_lits():
    # 2 + 3 => 5
    node = (ast.IntExpr.make(2) + ast.IntExpr.make(3)).node
    result = run_transform(ConstFoldPass, node)
    assert isinstance(result, ir.Lit) and result.val == 5


def test_prod_lits():
    # 4 * 7 => 28
    node = (ast.IntExpr.make(4) * ast.IntExpr.make(7)).node
    result = run_transform(ConstFoldPass, node)
    assert isinstance(result, ir.Lit) and result.val == 28


def test_neg_lit():
    # -5 => -5
    node = (-ast.IntExpr.make(5)).node
    result = run_transform(ConstFoldPass, node)
    assert isinstance(result, ir.Lit) and result.val == -5


def test_floordiv_lits():
    # 7 // 2 => 3
    node = (ast.IntExpr.make(7) // ast.IntExpr.make(2)).node
    result = run_transform(ConstFoldPass, node)
    assert isinstance(result, ir.Lit) and result.val == 3


def test_mod_lits():
    # 7 % 3 => 1
    node = (ast.IntExpr.make(7) % ast.IntExpr.make(3)).node
    result = run_transform(ConstFoldPass, node)
    assert isinstance(result, ir.Lit) and result.val == 1


def test_eq_lits():
    # 3 == 3 => True
    node = ir.Eq(ir.BoolT(), ast.IntExpr.make(3).node, ast.IntExpr.make(3).node)
    result = run_transform(ConstFoldPass, node)
    assert isinstance(result, ir.Lit) and result.val == True


def test_conj_lits():
    # True & False => False
    node = (ast.BoolExpr.make(True) & ast.BoolExpr.make(False)).node
    result = run_transform(ConstFoldPass, node)
    assert isinstance(result, ir.Lit) and result.val == False


def test_disj_lits():
    # True | False => True
    node = (ast.BoolExpr.make(True) | ast.BoolExpr.make(False)).node
    result = run_transform(ConstFoldPass, node)
    assert isinstance(result, ir.Lit) and result.val == True


def test_no_fold_symbolic():
    # x + 3 stays as Sum when x is symbolic
    from puzzlespec import var
    x = var(Int, name='x')
    node = (x + 3).node
    result = run_transform(ConstFoldPass, node)
    assert isinstance(result, ir.Sum)


def test_ismember_universe():
    # x in Universe => True
    from puzzlespec import var
    x = var(Int, name='x')
    univ = Int.U
    node = ir.IsMember(ir.BoolT(), univ.node, x.node)
    result = run_transform(ConstFoldPass, node)
    assert isinstance(result, ir.Lit) and result.val == True
