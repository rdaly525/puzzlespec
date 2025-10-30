from __future__ import annotations

import typing as tp
import numpy as np
from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir, ir_types as irT
from functools import reduce
import itertools as it

class VarMap(AnalysisObject):
    def __init__(self, varmap: tp.Dict[int, tp.Any]):
        self.varmap = varmap

class EvalResult(AnalysisObject):
    def __init__(self, res):
        self.result = res

class EvalPass(Analysis):
    requires = (VarMap,)
    produces = (EvalResult,)  
    name = "evaluator"

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        """Main entry point for the analysis pass."""
        self.varmap = ctx.get(VarMap).varmap
        self.bvars = []
        return EvalResult(self.visit(root))

    # Literals and basic nodes
    @handles(ir.Lit)
    def _(self, node: ir.Lit) -> tp.Any:
        """Analyze literal nodes."""
        return node.val

    @handles(mark_invalid=True)
    def _(self, node: ir._Param) -> tp.Any:
        """Analyze parameter nodes."""
        # TODO: Implement analysis for _Param nodes
        return node.name

    @handles()
    def _(self, node: ir.VarRef) -> tp.Any:
        """Analyze variable reference nodes."""
        if node.sid not in self.varmap:
            raise ValueError(f"Variable {node.sid} not found in varmap")
        return self.varmap[node.sid]

    @handles()
    def _(self, node: ir.BoundVar) -> tp.Any:
        """Analyze bound variable nodes."""
        return self.bvars[-node.idx-1]

    @handles(ir.Lambda)
    def _(self, node: ir.Lambda) -> tp.Any:
        """Analyze lambda nodes."""
        def lambda_fn(x):
            self.bvars.append(x)
            body, = self.visit_children(node)
            self.bvars.pop()
            return body
        return lambda_fn

    @handles(mark_invalid=True)
    def _(self, node: ir._BoundVarPlaceholder) -> tp.Any:
        """Analyze bound variable placeholder nodes."""
        # TODO: Implement analysis for _BoundVarPlaceholder nodes
        return None

    # Arithmetic + Boolean
    @handles(ir.Eq)
    def _(self, node: ir.Eq) -> tp.Any:
        """Analyze equality nodes."""
        left, right = self.visit_children(node)
        return left == right

    @handles(ir.And)
    def _(self, node: ir.And) -> tp.Any:
        """Analyze logical AND nodes."""
        left, right = self.visit_children(node)
        return left & right

    @handles(ir.Implies)
    def _(self, node: ir.Implies) -> tp.Any:
        """Analyze implication nodes."""
        left, right = self.visit_children(node)
        return ~left | right

    @handles(ir.Or)
    def _(self, node: ir.Or) -> tp.Any:
        """Analyze logical OR nodes."""
        left, right = self.visit_children(node)
        return left | right

    @handles(ir.Not)
    def _(self, node: ir.Not) -> tp.Any:
        """Analyze logical NOT nodes."""
        child, = self.visit_children(node)
        return ~child

    @handles(ir.Neg)
    def _(self, node: ir.Neg) -> tp.Any:
        """Analyze negation nodes."""
        child, = self.visit_children(node)
        return -child

    @handles(ir.Add)
    def _(self, node: ir.Add) -> tp.Any:
        """Analyze addition nodes."""
        left, right = self.visit_children(node)
        return left + right

    @handles(ir.Sub)
    def _(self, node: ir.Sub) -> tp.Any:
        """Analyze subtraction nodes."""
        left, right = self.visit_children(node)
        return left - right

    @handles(ir.Mul)
    def _(self, node: ir.Mul) -> tp.Any:
        """Analyze multiplication nodes."""
        left, right = self.visit_children(node)
        return left * right

    @handles(ir.Div)
    def _(self, node: ir.Div) -> tp.Any:
        """Analyze division nodes."""
        left, right = self.visit_children(node)
        return left // right

    @handles(ir.Mod)
    def _(self, node: ir.Mod) -> tp.Any:
        """Analyze modulo nodes."""
        left, right = self.visit_children(node)
        return left % right

    @handles(ir.Gt)
    def _(self, node: ir.Gt) -> tp.Any:
        """Analyze greater than nodes."""
        # TODO: Implement analysis for Gt nodes
        left, right = self.visit_children(node)
        return left > right

    @handles(ir.GtEq)
    def _(self, node: ir.GtEq) -> tp.Any:
        """Analyze greater than or equal nodes."""
        left, right = self.visit_children(node)
        return left >= right

    @handles(ir.Lt)
    def _(self, node: ir.Lt) -> tp.Any:
        """Analyze less than nodes."""
        left, right = self.visit_children(node)
        return left < right

    @handles(ir.LtEq)
    def _(self, node: ir.LtEq) -> tp.Any:
        """Analyze less than or equal nodes."""
        left, right = self.visit_children(node)
        return left <= right

    # Variadic
    @handles(ir.Conj)
    def _(self, node: ir.Conj) -> tp.Any:
        """Analyze conjunction nodes."""
        children = self.visit_children(node)
        return reduce(lambda a, b: a & b, children, True)

    @handles(ir.Disj)
    def _(self, node: ir.Disj) -> tp.Any:
        """Analyze disjunction nodes."""
        children = self.visit_children(node)
        return reduce(lambda a, b: a | b, children, False)

    @handles(ir.Sum)
    def _(self, node: ir.Sum) -> tp.Any:
        """Analyze sum nodes."""
        children = self.visit_children(node)
        return sum(children)

    @handles(ir.Prod)
    def _(self, node: ir.Prod) -> tp.Any:
        """Analyze product nodes."""
        children = self.visit_children(node)
        return reduce(lambda a, b: a * b, children, 1)

    # Collections - Tuple nodes
    @handles(ir.Tuple)
    def _(self, node: ir.Tuple) -> tp.Any:
        """Analyze tuple nodes."""
        children = self.visit_children(node)
        return tuple(children)

    @handles(ir.TupleGet)
    def _(self, node: ir.TupleGet) -> tp.Any:
        """Analyze tuple get nodes."""
        tup = self.visit_children(node)
        return tup[node.idx]

    # Collections - List nodes
    @handles(ir.List)
    def _(self, node: ir.List) -> tp.Any:
        """Analyze list nodes."""
        children = self.visit_children(node)
        return list(children)

    @handles(ir.ListTabulate)
    def _(self, node: ir.ListTabulate) -> tp.Any:
        """Analyze list tabulate nodes."""
        size, fun = self.visit_children(node)
        return [fun(i) for i in range(size)]

    @handles(ir.ListGet)
    def _(self, node: ir.ListGet) -> tp.Any:
        """Analyze list get nodes."""
        lst, idx = self.visit_children(node)
        return lst[idx]

    @handles(ir.ListLength)
    def _(self, node: ir.ListLength) -> tp.Any:
        """Analyze list length nodes."""
        list_vals, = self.visit_children(node)
        return len(list_vals)

    @handles(ir.ListWindow)
    def _(self, node: ir.ListWindow) -> tp.Any:
        """Analyze list window nodes."""
        lst, size, stride = self.visit_children(node)
        return [lst[i:i+size] for i in range(0, len(lst), stride)]

    @handles(ir.ListConcat)
    def _(self, node: ir.ListConcat) -> tp.Any:
        """Analyze list concatenation nodes."""
        a, b = self.visit_children(node)
        return a + b

    @handles(ir.ListContains)
    def _(self, node: ir.ListContains) -> tp.Any:
        """Analyze list contains nodes."""
        lst, elem = self.visit_children(node)
        return elem in lst

    @handles(ir.OnlyElement)
    def _(self, node: ir.OnlyElement) -> tp.Any:
        """Analyze only element nodes."""
        lst, = self.visit_children(node)
        return lst[0]

    # Collections - Dict nodes
    @handles(ir.Dict)
    def _(self, node: ir.Dict) -> tp.Any:
        """Analyze dictionary nodes."""
        keys, values = self.visit_children(node)
        return dict(zip(keys, values))

    @handles(ir.DictTabulate)
    def _(self, node: ir.DictTabulate) -> tp.Any:
        """Analyze dictionary tabulate nodes."""
        keys, fun = self.visit_children(node)
        return {k: fun(k) for k in keys}

    @handles(ir.DictGet)
    def _(self, node: ir.DictGet) -> tp.Any:
        """Analyze dictionary get nodes."""
        dct, key = self.visit_children(node)
        return dct[key]

    @handles(ir.DictMap)
    def _(self, node: ir.DictMap) -> tp.Any:
        """Analyze dictionary map nodes."""
        dct, fun = self.visit_children(node)
        return {k: fun((k, v)) for k, v in dct.items()}

    @handles(ir.DictLength)
    def _(self, node: ir.DictLength) -> tp.Any:
        """Analyze dictionary length nodes."""
        dct, = self.visit_children(node)
        return len(dct)

    # Grid nodes
    @handles(ir.Grid)
    def _(self, node: ir.Grid) -> tp.Any:
        """Analyze grid nodes."""
        elements = self.visit_children(node)
        return [[elements[r*node.nC + c] for c in range(node.nC)] for r in range(node.nR)]

    @handles(ir.GridTabulate)
    def _(self, node: ir.GridTabulate) -> tp.Any:
        """Analyze grid tabulate nodes."""
        nR, nC, fun = self.visit_children(node)
        return [[fun((r, c)) for c in range(nC)] for r in range(nR)]

    @handles(ir.GridEnumNode)
    def _(self, node: ir.GridEnumNode) -> tp.Any:
        """Analyze grid enumeration nodes."""
        nR, nC = self.visit_children(node)
        match node.cellT:
            case irT.CellIdxT:
                raise ValueError("CellIdxT must be concrete for GridEnumNode evaluation")
            case irT.TupleT(irT.Int, irT.Int):
                match node.mode:
                    case "Cells":
                        return [(r,c) for r,c in it.product(range(nR), range(nC))]
                    case "Rows" | "CellGrid":
                        return [[(r,c) for c in range(nC)] for r in range(nR)]
                    case "Cols":
                        return [(r,c) for r,c in it.product(range(nR), range(nC))]
                    case _:
                        raise ValueError(f"Unsupported mode: {node.mode}")
            case irT.Int:
                match node.mode:
                    case "Cells":
                        return list(range(nR*nC))
                    case "Rows" | "CellGrid":
                        return [[r*nC + c for c in range(nC)] for r in range(nR)]
                    case "Cols":
                        return [[r*nC + c for r in range(nR)] for c in range(nC)]
                    case _:
                        raise ValueError(f"Unsupported mode: {node.mode}")
            case _:
                raise ValueError(f"Unsupported cell type: {node.cellT}")

    @handles(ir.GridFlatNode)
    def _(self, node: ir.GridFlatNode) -> tp.Any:
        """Analyze grid flat nodes."""
        grid, = self.visit_children(node)
        return [elem for row in grid for elem in row]

    @handles(ir.GridWindowNode)
    def _(self, node: ir.GridWindowNode) -> tp.Any:
        """Analyze grid window nodes."""
        grid, size_r, size_c, stride_r, stride_c = self.visit_children(node)
        #TODO
        raise NotImplementedError("GridWindowNode evaluation not implemented")

    @handles(ir.GridDims)
    def _(self, node: ir.GridDims) -> tp.Any:
        """Analyze grid dimensions nodes."""
        grid, = self.visit_children(node)
        return (len(grid), len(grid[0]))

    @handles(mark_invalid=True)
    def _(self, node: ir._LambdaPlaceholder) -> tp.Any:
        """Analyze lambda placeholder nodes."""
        # TODO: Implement analysis for _LambdaPlaceholder nodes
        bound_var, body = self.visit_children(node)
        return (bound_var, body, node.paramT)

    @handles(ir.Map)
    def _(self, node: ir.Map) -> tp.Any:
        """Analyze map nodes."""
        domain, fun = self.visit_children(node)
        return [fun(elem) for elem in domain]

    @handles(ir.Fold)
    def _(self, node: ir.Fold) -> tp.Any:
        """Analyze fold nodes."""
        domain, fun, init = self.visit_children(node)
        return reduce(fun, domain, init)

    @handles(ir.SumReduce)
    def _(self, node: ir.SumReduce) -> tp.Any:
        """Analyze sum reduce nodes."""
        vals, = self.visit_children(node)
        return sum(vals)

    @handles(ir.ProdReduce)
    def _(self, node: ir.ProdReduce) -> tp.Any:
        """Analyze product reduce nodes."""
        vals, = self.visit_children(node)
        return reduce(lambda a, b: a * b, vals, 1)

    @handles(ir.Forall)
    def _(self, node: ir.Forall) -> tp.Any:
        """Analyze forall nodes."""
        domain, fun = self.visit_children(node)
        return reduce(lambda a, b: a & b, [fun(elem) for elem in domain], True)

    @handles(ir.Exists)
    def _(self, node: ir.Exists) -> tp.Any:
        """Analyze exists nodes."""
        domain, fun = self.visit_children(node)
        return reduce(lambda a, b: a | b, [fun(elem) for elem in domain], False)

    @handles(ir.Distinct)
    def _(self, node: ir.Distinct) -> tp.Any:
        """Analyze distinct nodes."""
        vals, = self.visit_children(node)
        return len(set(vals)) == len(vals)