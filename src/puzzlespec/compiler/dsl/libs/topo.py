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
    def cells(self) -> ast.GridDomExpr:
        return ast.GridDomExpr.make(self.nR, self.nC)
        
    def vertices(self) -> ast.GridDomExpr:
        return ast.GridDomExpr.make(self.nR+1, self.nC+1)

    # Vertical edges
    def edgesV(self) -> ast.GridDomExpr:
        return ast.GridDomExpr.make(self.nR, self.nC+1)

    # Horizontal edges
    def edgesH(self) -> ast.GridDomExpr:
        return ast.GridDomExpr.make(self.nR+1, self.nC)

    # Disjoint union of vertical and horizontal edges
    def edges(self) -> ast.DomainExpr:
        return self.edgesV() + self.edgesH()

    def CellIdxT(self) -> irT.Type_:
        return self.cells().carrier_type

    def VertexIdxT(self) -> irT.Type_:
        return self.vertices().carrier_type

    def EdgeVIdxT(self) -> irT.Type_:
        return self.edgesV().carrier_type

    def EdgeHIdxT(self) -> irT.Type_:
        return self.edgesH().carrier_type

    def EdgeIdxT(self) -> irT.Type_:
        return self.edges().carrier_type

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
