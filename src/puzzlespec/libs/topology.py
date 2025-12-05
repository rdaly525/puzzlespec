from ..compiler.dsl import ast, ast_nd, ir
import typing as tp
from abc import abstractmethod

fin = ast_nd.fin

class Topology:
    pass

class Grid2D(Topology):

    def __init__(self, nR: ast.IntOrExpr, nC: ast.IntOrExpr):
        nR, nC = ast.IntExpr.make(nR), ast.IntExpr.make(nC)
        self.nR = nR
        self.nC = nC

    # Cells
    def cells(self) -> ast_nd.NDSeqDomainExpr:
        return fin(self.nR) * fin(self.nC)

    def vertices(self) -> ast_nd.NDSeqDomainExpr:
        return fin(self.nR+1) * fin(self.nC+1)

    # Vertical edges
    def edgesV(self) -> ast_nd.NDSeqDomainExpr:
        return fin(self.nR) * fin(self.nC+1)

    # Horizontal edges
    def edgesH(self) -> ast_nd.NDSeqDomainExpr:
        return fin(self.nR+1) * fin(self.nC)

    # Disjoint union of vertical and horizontal edges
    def edges(self) -> ast.DomainExpr:
        return self.edgesV() + self.edgesH()

    @property
    def CellIdxT(self) -> ast.TExpr:
        return self.cells().T.carT

    @property
    def VertexIdxT(self) -> ast.TExpr:
        return self.vertices().T.carT

    @property
    def EdgeVIdxT(self) -> ast.TExpr:
        return self.edgesV().T.carT

    @property
    def EdgeHIdxT(self) -> ast.TExpr:
        return self.edgesH().T.carT

    @property
    def EdgeIdxT(self) -> ast.TExpr:
        return self.edges().T.carT

    ## relations among cells, vertices, edges

    #relation for 2 cells adjacent (4 means orthogonal, 8 means diagonal)
    def cell_adjacent(self, n: ast.IntOrExpr, c1: 'CellIdxT', c2:'CellIdxT') -> ast.BoolExpr:
        if type(c1.T) != type(self.CellIdxT) or type(c2.T) != type(self.CellIdxT):
            raise ValueError(f"c1 and c2 must be of type {self.CellIdxT}, got {c1.T} and {c2.T}")
        if n==4:
            delta = (abs(c1[0]-c2[0]), abs(c1[1]-c2[1]))
            return ((delta[0]==0) & (delta[1]==1)) | ((delta[0]==1) & (delta[1]==0))
        elif n==8:
            delta = (abs(c1[0]-c2[0]), abs(c1[1]-c2[1]))
            # cannot be the same cell and adj must be at most 1
            return (c1!=c2) & (delta[0]<=1) & (delta[1]<=1)
        else:
            raise ValueError(f"n must be 4 or 8, got {n}")
