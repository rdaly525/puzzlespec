from .. import ast, ir, ir_types as irT
import typing as tp
from abc import abstractmethod

class Topology:
    pass

class Grid2D(Topology):

    def __init__(self, nR: ast.IntOrExpr, nC: ast.IntOrExpr):
        nR, nC = ast.IntExpr.make(nR), ast.IntExpr.make(nC)
        self.nR = nR
        self.nC = nC

    # Cells
    def cells(self) -> ast.NDSeqDomainExpr:
        return self.nR.fin() * self.nC.fin()

    def vertices(self) -> ast.NDSeqDomainExpr:
        return (self.nR+1).fin() * (self.nC+1).fin()

    # Vertical edges
    def edgesV(self) -> ast.NDSeqDomainExpr:
        return self.nR.fin() * (self.nC+1).fin()

    # Horizontal edges
    def edgesH(self) -> ast.NDSeqDomainExpr:
        return (self.nR+1).fin() * self.nC.fin()

    # Disjoint union of vertical and horizontal edges
    def edges(self) -> ast.DomainExpr:
        return self.edgesV() + self.edgesH()

    @property
    def CellIdxT(self) -> irT.Type_:
        return self.cells().carT

    @property
    def VertexIdxT(self) -> irT.Type_:
        return self.vertices().carT

    @property
    def EdgeVIdxT(self) -> irT.Type_:
        return self.edgesV().carT

    @property
    def EdgeHIdxT(self) -> irT.Type_:
        return self.edgesH().carT

    @property
    def EdgeIdxT(self) -> irT.Type_:
        return self.edges().carT

    ### relations among cells, vertices, edges

    # relation for 2 cells adjacent (4 means orthogonal, 8 means diagonal)
    def cell_adjacent(self, n: ast.IntOrExpr, c1: 'CellIdxT', c2:'CellIdxT') -> ast.BoolExpr:
        if n==4:
            delta = (abs(c1[0]-c2[0]), abs(c1[1]-c2[1]))
            return ((delta[0]==0) & (delta[1]==1)) | ((delta[0]==1) & (delta[1]==0))
        elif n==8:
            delta = (abs(c1[0]-c2[0]), abs(c1[1]-c2[1]))
            # cannot be the same cell and adj must be at most 1
            return (c1!=c2) & (delta[0]<=1) & (delta[1]<=1)
        else:
            raise ValueError(f"n must be 4 or 8, got {n}")
