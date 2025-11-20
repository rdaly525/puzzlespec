from __future__ import annotations

import typing as tp
import numpy as np
from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir
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
    @handles()
    def _(self, node: ir.Unit) -> tp.Any:
        """Analyze unit nodes."""
        return None

    @handles()
    def _(self, node: ir.Lit) -> tp.Any:
        """Analyze literal nodes."""
        return node.val

    # Note: _Param node no longer exists in ir.py

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
        raise NotImplementedError("_BoundVarPlaceholder evaluation should be handled after transformation to BoundVar")

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

    @handles()
    def _(self, node: ir.Ite) -> tp.Any:
        """Analyze if-then-else nodes."""
        pred, t, f = self.visit_children(node)
        return t if pred else f

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

    ## Domains
    @handles()
    def _(self, node: ir.Universe) -> tp.Any:
        """Analyze universe domain nodes."""
        # TODO: Determine how to evaluate Universe domain
        raise NotImplementedError("Universe domain evaluation not implemented")

    @handles()
    def _(self, node: ir.Fin) -> tp.Any:
        """Analyze finite domain nodes."""
        n, = self.visit_children(node)
        return list(range(n))

    @handles()
    def _(self, node: ir.Enum) -> tp.Any:
        """Analyze enum domain nodes."""
        # TODO: Determine how to evaluate Enum domain
        return list(node.enumT.labels)

    @handles()
    def _(self, node: ir.EnumLit) -> tp.Any:
        """Analyze enum literal nodes."""
        return node.label

    @handles()
    def _(self, node: ir.Card) -> tp.Any:
        """Analyze cardinality nodes."""
        domain, = self.visit_children(node)
        return len(domain)

    @handles()
    def _(self, node: ir.IsMember) -> tp.Any:
        """Analyze is member nodes."""
        domain, val = self.visit_children(node)
        return val in domain

    ## Cartesian Products
    @handles()
    def _(self, node: ir.CartProd) -> tp.Any:
        """Analyze cartesian product nodes."""
        doms = self.visit_children(node)
        # TODO: Determine how to evaluate CartProd - may need to generate all combinations
        return list(it.product(*doms))

    @handles()
    def _(self, node: ir.DomProj) -> tp.Any:
        """Analyze domain projection nodes."""
        # TODO: Determine how to evaluate DomProj
        raise NotImplementedError("DomProj evaluation not implemented")

    # Collections - Tuple nodes
    @handles()
    def _(self, node: ir.TupleLit) -> tp.Any:
        """Analyze tuple literal nodes."""
        children = self.visit_children(node)
        return tuple(children)

    @handles()
    def _(self, node: ir.Proj) -> tp.Any:
        """Analyze projection nodes."""
        tup, = self.visit_children(node)
        return tup[node.idx]

    @handles()
    def _(self, node: ir.DisjUnion) -> tp.Any:
        """Analyze disjoint union nodes."""
        # TODO: Determine how to evaluate DisjUnion
        raise NotImplementedError("DisjUnion evaluation not implemented")

    @handles()
    def _(self, node: ir.DomInj) -> tp.Any:
        """Analyze domain injection nodes."""
        # TODO: Determine how to evaluate DomInj
        raise NotImplementedError("DomInj evaluation not implemented")

    @handles()
    def _(self, node: ir.Inj) -> tp.Any:
        """Analyze injection nodes."""
        # TODO: Determine how to evaluate Inj
        raise NotImplementedError("Inj evaluation not implemented")

    @handles()
    def _(self, node: ir.Match) -> tp.Any:
        """Analyze match nodes."""
        # TODO: Determine how to evaluate Match
        scrut, branches = self.visit_children(node)
        raise NotImplementedError("Match evaluation not implemented")

    @handles()
    def _(self, node: ir.Restrict) -> tp.Any:
        """Analyze restrict nodes."""
        domain, pred = self.visit_children(node)
        # pred is a Lambda function
        return [elem for elem in domain if pred(elem)]

    ## Funcs (i.e., containers)
    @handles()
    def _(self, node: ir.Map) -> tp.Any:
        """Analyze tabulate nodes."""
        dom, fun = self.visit_children(node)
        # fun is a Lambda function
        return [fun(elem) for elem in dom]

    @handles()
    def _(self, node: ir.Image) -> tp.Any:
        """Analyze image of function nodes."""
        func, = self.visit_children(node)
        # TODO: Determine how to extract image from function
        if isinstance(func, dict):
            return list(func.values())
        elif isinstance(func, list):
            return func
        else:
            raise NotImplementedError(f"ImageOf evaluation for {type(func)} not implemented")

    @handles()
    def _(self, node: ir.Apply) -> tp.Any:
        """Analyze apply nodes."""
        func, arg = self.visit_children(node)
        if isinstance(func, dict):
            return func[arg]
        elif isinstance(func, list):
            return func[arg]
        elif callable(func):
            return func(arg)
        else:
            raise NotImplementedError(f"Apply evaluation for {type(func)} not implemented")

    @handles()
    def _(self, node: ir.ListLit) -> tp.Any:
        """Analyze list literal nodes."""
        children = self.visit_children(node)
        return list(children)

    @handles()
    def _(self, node: ir.Index) -> tp.Any:
        """Analyze windows nodes."""
        lst, size, stride = self.visit_children(node)
        return [lst[i:i+size] for i in range(0, len(lst), stride)]

    @handles()
    def _(self, node: ir.Slice) -> tp.Any:
        """Analyze tiles nodes."""
        # TODO: Determine how to evaluate Tiles - sizes and strides are tuples
        dom, sizes, strides = self.visit_children(node)
        raise NotImplementedError("Tiles evaluation not implemented")

    @handles(mark_invalid=True)
    def _(self, node: ir._LambdaPlaceholder) -> tp.Any:
        """Analyze lambda placeholder nodes."""
        # TODO: Implement analysis for _LambdaPlaceholder nodes
        raise NotImplementedError("_LambdaPlaceholder evaluation should be handled after transformation")

    @handles()
    def _(self, node: ir.Fold) -> tp.Any:
        """Analyze fold nodes."""
        # Fold signature: func: Func, fun: Lambda, init: value
        func, fun, init = self.visit_children(node)
        # fun is a Lambda function that takes (acc, elem) -> acc
        # func is a list or dict representing the function
        # TODO: Determine correct iteration order for Fold
        if isinstance(func, dict):
            # For dicts, fold over values
            domain = list(func.values())
        elif isinstance(func, list):
            # For lists, fold over elements
            domain = func
        else:
            raise NotImplementedError(f"Fold evaluation for {type(func)} not implemented")
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

    @handles()
    def _(self, node: ir.Forall) -> tp.Any:
        """Analyze forall nodes."""
        domain, fun = self.visit_children(node)
        # fun is a Lambda function
        return reduce(lambda a, b: a & b, [fun(elem) for elem in domain], True)

    @handles()
    def _(self, node: ir.Exists) -> tp.Any:
        """Analyze exists nodes."""
        domain, fun = self.visit_children(node)
        # fun is a Lambda function
        return reduce(lambda a, b: a | b, [fun(elem) for elem in domain], False)

    @handles(ir.AllDistinct)
    def _(self, node: ir.AllDistinct) -> tp.Any:
        """Analyze distinct nodes."""
        vals, = self.visit_children(node)
        return len(set(vals)) == len(vals)

    @handles(ir.AllSame)
    def _(self, node: ir.AllSame) -> tp.Any:
        """Analyze Same nodes."""
        vals, = self.visit_children(node)
        return len(set(vals)) == 1