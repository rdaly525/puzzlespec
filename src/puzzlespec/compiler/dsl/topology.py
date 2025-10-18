from . import ast, ir_types as irT
from . import ir
import typing as tp
from abc import abstractmethod

class Topology:
    @abstractmethod
    def terms(self) -> ast.Expr:
        ...

    def terms_node(self) -> ir.Node:
        return self.terms.node

class Grid2D(Topology):
    def __init__(self, nR: ast.IntOrExpr, nC: ast.IntOrExpr):
        nR, nC = ast.IntExpr.make(nR), ast.IntExpr.make(nC)
        self.nR = nR
        self.nC = nC

    @classmethod
    def make_from_terms_node(cls, dims: ir.Tuple) -> 'Grid2D':
        if not isinstance(dims, ir.Tuple) and len(dims._children) != 2:
            raise ValueError(f"Grid2D expects an ir.Tuple of 2 ints, but got {dims}")
        nR = ast.IntExpr(dims._children[0], irT.Int)
        nC = ast.IntExpr(dims._children[1], irT.Int)
        return Grid2D(nR, nC)

    def terms_node(self) -> ir.Tuple:
        return ir.Tuple(self.nR.node, self.nC.node)

    def index_grid(self, mode:str) -> ast.GridExpr[ast.Expr]:
        if mode == "C":
            idx_lambda = ast.make_lambda(lambda c: c, irT.CellIdxT)
            node = ir.GridTabulate(self.nR.node, self.nC.node, idx_lambda.node)
            return ast.wrap(node, irT.GridT(irT.CellIdxT, "C"))
        raise NotImplementedError(f"Grid2D.index_grid: mode={mode} not implemented")

    # Cells
    def C(self) -> ast.ListExpr[ast.Expr]:
        node = ir.GridEnumNode(self.nR.node, self.nC.node, "Cells")
        T = irT.ListT(irT.CellIdxT)
        return tp.cast(ast.ListExpr[ast.Expr], ast.wrap(node, T))
    
    def rows(self) -> ast.ListExpr[ast.ListExpr[ast.Expr]]:
        node = ir.GridEnumNode(self.nR.node, self.nC.node, "Rows")
        T = irT.ListT(irT.ListT(irT.CellIdxT))
        return tp.cast(ast.ListExpr[ast.ListExpr[ast.Expr]], ast.wrap(node, T))

    def cols(self) -> ast.ListExpr[ast.ListExpr[ast.Expr]]:
        node = ir.GridEnumNode(self.nR.node, self.nC.node, "Cols")
        T = irT.ListT(irT.ListT(irT.CellIdxT))
        return tp.cast(ast.ListExpr[ast.ListExpr[ast.Expr]], ast.wrap(node, T))

    def Cells(self, grid=False):
        if grid:
            node = ir.GridEnumNode(self.nR.node, self.nC.node, "CellGrid")
            T = irT.GridT(irT.CellIdxT, "C")
            return tp.cast(ast.GridExpr[ast.Expr], ast.wrap(node, T))
        else:
            return self.C()

    def tiles(self, size: tp.Tuple[ast.IntOrExpr, ast.IntOrExpr], stride: tp.Tuple[ast.IntOrExpr, ast.IntOrExpr]) -> ast.ListExpr[ast.GridExpr[ast.Expr]]:
        cell_grid = self.Cells(grid=True)
        return cell_grid.tiles(size, stride)