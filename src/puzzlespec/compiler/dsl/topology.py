from . import ast, ir_types as irT
from . import ir
import typing as tp

class Topology:
    def terms(self) -> tp.List[ast.Expr]:
        ...

class Grid2D(Topology):
    def __init__(self, nR: ast.IntOrExpr, nC: ast.IntOrExpr):
        self.nR = ast.IntExpr.make(nR)
        self.nC = ast.IntExpr.make(nC)

    def copy(self):
        return Grid2D(self.nR, self.nC)

    def terms(self):
        return [self.nR, self.nC]

    def index_grid(self, mode:str) -> ast.GridExpr[ast.Expr]:
        if mode == "C":
            idx_lambda = ast.make_lambda(lambda c: c, irT.CellIdxT)
            node = ir.GridTabulate(self.nR.node, self.nC.node, idx_lambda.node)
            return ast.wrap(node, irT.GridT(irT.CellIdxT, "C"))
        raise NotImplementedError(f"Grid2D.index_grid: mode={mode} not implemented")

    def C(self) -> ast.ListExpr[ast.Expr]:
        node = ir.GridEnumNode(self.nR.node, self.nC.node, "C")
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
    
    def tiles(self, size: tp.Tuple[ast.IntOrExpr, ast.IntOrExpr], stride: tp.Tuple[ast.IntOrExpr, ast.IntOrExpr]) -> ast.ListExpr[ast.GridExpr[ast.Expr]]:
        id_grid = tp.cast(ast.GridExpr[ast.Expr], self.index_grid("C"))
        return id_grid.tiles(size, stride)