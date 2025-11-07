from __future__ import annotations

from ..pass_base import Context, AnalysisObject, Analysis, handles
from ..envobj import EnvsObj
from ...dsl import ir, ir_types as irT
import typing as tp

if tp.TYPE_CHECKING:
    from ...dsl import spec


class TypeValues(AnalysisObject):
    def __init__(self, mapping):
        self.mapping: tp.Dict[ir.Node, irT.Type_] = mapping


class TypeInferencePass(Analysis):
    #_debug=True
    requires = (EnvsObj,)
    produces = (TypeValues,)
    name = "type_inference"
    
    def __init__(self):
        super().__init__()

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.tenv: tp.Dict[int, irT.Type_] = ctx.get(EnvsObj).tenv.vars
        self.bctx: tp.List[irT.Type_] = []
        # Walk and populate
        root_T = self.visit(root)
        tv = TypeValues(self._cache)
        return tv

    def visit(self, node):
        raise ValueError(f"Should never occur! {node}")
        # All visitors have been defined

    ##############################
    ## Core-level IR nodes (Used throughout entire compiler flow)
    ##############################

    @handles(ir.Unit)
    def _(self, node: ir.Unit):
        return irT.UnitType

    @handles(ir.VarRef)
    def _(self, node: ir.VarRef):
        if node.sid not in self.tenv:
            raise TypeError(f"Variable with sid={node.sid} not found in type environment")
        return self.tenv[node.sid]

    @handles(ir.BoundVar)
    def _(self, node: ir.BoundVar):
        if node.idx >= len(self.bctx):
            raise TypeError(f"BoundVar index {node.idx} out of bounds (bctx length: {len(self.bctx)})")
        return self.bctx[-(node.idx+1)]

    @handles(ir.Lambda)
    def _(self, node: ir.Lambda):
        self.bctx.append(node.paramT)
        bodyT, = self.visit_children(node)
        self.bctx.pop()
        return irT.ArrowT(node.paramT, bodyT)

    @handles(ir.Lit)
    def _(self, node: ir.Lit):
        return node.T

    @handles(ir.Eq)
    def _(self, node: ir.Eq):
        leftT, rightT = self.visit_children(node)
        if leftT != rightT:
            raise TypeError(f"Eq has children of inconsistent types: {leftT} != {rightT}")
        return irT.Bool

    @handles(ir.Lt)
    def _(self, node: ir.Lt):
        leftT, rightT = self.visit_children(node)
        if leftT != irT.Int or rightT != irT.Int:
            raise TypeError(f"Lt expects Int operands, got {leftT} and {rightT}")
        return irT.Bool

    @handles(ir.LtEq)
    def _(self, node: ir.LtEq):
        leftT, rightT = self.visit_children(node)
        if leftT != irT.Int or rightT != irT.Int:
            raise TypeError(f"LtEq expects Int operands, got {leftT} and {rightT}")
        return irT.Bool

    @handles(ir.Ite)
    def _(self, node: ir.Ite):
        predT, tT, fT = self.visit_children(node)
        if predT != irT.Bool:
            raise TypeError(f"Ite predicate must be Bool, got {predT}")
        if tT != fT:
            raise TypeError(f"Ite branches must have same type: {tT} != {fT}")
        return tT

    @handles(ir.Not)
    def _(self, node: ir.Not):
        childT, = self.visit_children(node)
        if childT != irT.Bool:
            raise TypeError(f"Not expects Bool, got {childT}")
        return irT.Bool

    @handles(ir.Neg)
    def _(self, node: ir.Neg):
        childT, = self.visit_children(node)
        if childT != irT.Int:
            raise TypeError(f"Neg expects Int, got {childT}")
        return irT.Int

    @handles(ir.Div)
    def _(self, node: ir.Div):
        leftT, rightT = self.visit_children(node)
        if leftT != irT.Int or rightT != irT.Int:
            raise TypeError(f"Div expects Int operands, got {leftT} and {rightT}")
        return irT.Int

    @handles(ir.Mod)
    def _(self, node: ir.Mod):
        leftT, rightT = self.visit_children(node)
        if leftT != irT.Int or rightT != irT.Int:
            raise TypeError(f"Mod expects Int operands, got {leftT} and {rightT}")
        return irT.Int

    @handles(ir.Conj)
    def _(self, node: ir.Conj):
        childTs = self.visit_children(node)
        for child, childT in zip(node._children, childTs):
            if childT != irT.Bool:
                raise TypeError(f"Conj child {child} must be Bool, got {childT}")
        return irT.Bool

    @handles(ir.Disj)
    def _(self, node: ir.Disj):
        childTs = self.visit_children(node)
        for child, childT in zip(node._children, childTs):
            if childT != irT.Bool:
                raise TypeError(f"Disj child {child} must be Bool, got {childT}")
        return irT.Bool

    @handles(ir.Sum)
    def _(self, node: ir.Sum):
        childTs = self.visit_children(node)
        for child, childT in zip(node._children, childTs):
            if childT != irT.Int:
                raise TypeError(f"Sum child {child} must be Int, got {childT}")
        return irT.Int

    @handles(ir.Prod)
    def _(self, node: ir.Prod):
        childTs = self.visit_children(node)
        for child, childT in zip(node._children, childTs):
            if childT != irT.Int:
                raise TypeError(f"Prod child {child} must be Int, got {childT}")
        return irT.Int

    @handles(ir.Universe)
    def _(self, node: ir.Universe):
        return irT.DomT(node.T, irT.DomCap())

    @handles(ir.Fin)
    def _(self, node: ir.Fin):
        NT, = self.visit_children(node)
        if NT != irT.Int:
            raise TypeError(f"Fin expects Int argument, got {NT}")
        # TODO: Verify the domain type construction
        return irT.DomT(irT.Int, irT.DomCap(finite=True, enumerable=1, ordered=True))

    @handles(ir.Card)
    def _(self, node: ir.Card):
        domT, = self.visit_children(node)
        if not isinstance(domT, irT.DomT):
            raise TypeError(f"Card expects DomT, got {domT}")
        return irT.Int

    @handles(ir.IsMember)
    def _(self, node: ir.IsMember):
        domT, valT = self.visit_children(node)
        if not isinstance(domT, irT.DomT):
            raise TypeError(f"IsMember expects DomT as first argument, got {domT}")
        if valT != domT.carT:
            raise TypeError(f"IsMember value type {valT} does not match domain carrier type {domT.carT}")
        return irT.Bool

    @handles(ir.CartProd)
    def _(self, node: ir.CartProd):
        domTs = self.visit_children(node)
        for domT in domTs:
            if not isinstance(domT, irT.DomT):
                raise TypeError(f"CartProd expects DomT arguments, got {domT}")
        # TODO: Verify cartesian product domain construction
        # The carrier type should be a tuple of the carrier types
        carTs = tuple(domT.carT for domT in domTs)
        carT = irT.TupleT(*carTs) if len(carTs) > 1 else carTs[0] if len(carTs) == 1 else irT.UnitType
        # TODO: What should the capabilities be?
        return irT.DomT(carT, irT.DomCap())

    @handles(ir.DomProj)
    def _(self, node: ir.DomProj):

        domT, = self.visit_children(node)
        if not isinstance(domT, irT.DomT):
            raise TypeError(f"DomProj expects DomT, got {domT}")
        # TODO: Verify domain projection - should extract one component from cartesian product
        if not isinstance(domT.carT, irT.TupleT):
            raise TypeError(f"DomProj expects tuple carrier type, got {domT.carT}")
        if node.idx >= len(domT.carT.elemTs):
            raise TypeError(f"DomProj index {node.idx} out of bounds for tuple of length {len(domT.carT.elemTs)}")
        return irT.DomT(domT.carT.elemTs[node.idx], domT.cap)

    @handles(ir.TupleLit)
    def _(self, node: ir.TupleLit):
        childTs = self.visit_children(node)
        return irT.TupleT(*childTs)

    @handles(ir.Proj)
    def _(self, node: ir.Proj):
        tupT, = self.visit_children(node)
        if not isinstance(tupT, irT.TupleT):
            raise TypeError(f"Proj expects TupleT, got {tupT}")
        if node.idx >= len(tupT.elemTs):
            raise TypeError(f"Proj index {node.idx} out of bounds for tuple of length {len(tupT.elemTs)}")
        return tupT.elemTs[node.idx]

    @handles(ir.DisjUnion)
    def _(self, node: ir.DisjUnion):
        domTs = self.visit_children(node)
        for domT in domTs:
            if not isinstance(domT, irT.DomT):
                raise TypeError(f"DisjUnion expects DomT arguments, got {domT}")
        # TODO: Verify disjoint union construction
        # The carrier type should be a sum type
        carTs = tuple(domT.carT for domT in domTs)
        carT = irT.SumT(*carTs) if len(carTs) > 0 else irT.UnitType
        # TODO: What should the capabilities be?
        return irT.DomT(carT, irT.DomCap())

    @handles(ir.DomInj)
    def _(self, node: ir.DomInj):
        domT, = self.visit_children(node)
        if not isinstance(domT, irT.DomT):
            raise TypeError(f"DomInj expects DomT, got {domT}")
        # TODO: Verify domain injection - should inject into one component of disjoint union
        if not isinstance(domT.carT, irT.SumT):
            raise TypeError(f"DomInj expects sum carrier type, got {domT.carT}")
        if node.idx >= len(domT.carT.elemTs):
            raise TypeError(f"DomInj index {node.idx} out of bounds for sum of length {len(domT.carT.elemTs)}")
        if domT.carT.elemTs[node.idx] != node.T:
            raise TypeError(f"DomInj type mismatch: expected {domT.carT.elemTs[node.idx]}, got {node.T}")
        return irT.DomT(node.T, domT.cap)

    @handles(ir.Inj)
    def _(self, node: ir.Inj):
        valT, = self.visit_children(node)
        if valT != node.T:
            raise TypeError(f"Inj value type {valT} does not match node type {node.T}")
        # TODO: Verify injection type - should construct sum type
        # The result should be a sum type containing node.T at index node.idx
        # But we don't know the full sum type from just this node
        return irT.SumT(node.T)  # TODO: This is likely incomplete

    @handles(ir.Match)
    def _(self, node: ir.Match):
        scrutT, branchesT = self.visit_children(node)
        # TODO: Verify match node structure
        # scrutinee should be a sum type
        if not isinstance(scrutT, irT.SumT):
            raise TypeError(f"Match scrutinee must be SumT, got {scrutT}")
        # branches should be a tuple of lambdas
        if not isinstance(branchesT, irT.TupleT):
            raise TypeError(f"Match branches must be TupleT, got {branchesT}")
        if len(branchesT.elemTs) != len(scrutT.elemTs):
            raise TypeError(f"Match branches count {len(branchesT.elemTs)} does not match sum type count {len(scrutT.elemTs)}")
        # Verify each branch is an ArrowT matching the corresponding sum component
        branchTs = branchesT.elemTs
        if len(branchTs) == 0:
            raise TypeError("Match must have at least one branch")
        resT = None
        for i, (sumElemT, branchT) in enumerate(zip(scrutT.elemTs, branchTs)):
            if not isinstance(branchT, irT.ArrowT):
                raise TypeError(f"Match branch {i} must be ArrowT, got {branchT}")
            if branchT.argT != sumElemT:
                raise TypeError(f"Match branch {i} argument type {branchT.argT} does not match sum component {sumElemT}")
            if resT is None:
                resT = branchT.resT
            elif branchT.resT != resT:
                raise TypeError(f"Match branches must have same result type: {resT} != {branchT.resT}")
        return resT

    @handles(ir.Restrict)
    def _(self, node: ir.Restrict):
        domT, predT = self.visit_children(node)
        if not isinstance(domT, irT.DomT):
            raise TypeError(f"Restrict expects DomT as first argument, got {domT}")
        if not isinstance(predT, irT.ArrowT):
            raise TypeError(f"Restrict expects ArrowT as second argument, got {predT}")
        if predT.argT != domT.carT:
            raise TypeError(f"Restrict predicate argument type {predT.argT} does not match domain carrier type {domT.carT}")
        if predT.resT != irT.Bool:
            raise TypeError(f"Restrict predicate must return Bool, got {predT.resT}")
        return domT

    @handles(ir.Forall)
    def _(self, node: ir.Forall):
        domT, funT = self.visit_children(node)
        if not isinstance(domT, irT.DomT):
            raise TypeError(f"Forall expects DomT as first argument, got {domT}")
        if not isinstance(funT, irT.ArrowT):
            raise TypeError(f"Forall expects ArrowT as second argument, got {funT}")
        if funT.argT != domT.carT:
            raise TypeError(f"Forall function argument type {funT.argT} does not match domain carrier type {domT.carT}")
        if funT.resT != irT.Bool:
            raise TypeError(f"Forall function must return Bool, got {funT.resT}")
        return irT.Bool

    @handles(ir.Exists)
    def _(self, node: ir.Exists):
        domT, funT = self.visit_children(node)
        if not isinstance(domT, irT.DomT):
            raise TypeError(f"Exists expects DomT as first argument, got {domT}")
        if not isinstance(funT, irT.ArrowT):
            raise TypeError(f"Exists expects ArrowT as second argument, got {funT}")
        if funT.argT != domT.carT:
            raise TypeError(f"Exists function argument type {funT.argT} does not match domain carrier type {domT.carT}")
        if funT.resT != irT.Bool:
            raise TypeError(f"Exists function must return Bool, got {funT.resT}")
        return irT.Bool

    @handles(ir.Tabulate)
    def _(self, node: ir.Tabulate):
        domT, funT = self.visit_children(node)
        if not isinstance(domT, irT.DomT):
            raise TypeError(f"Tabulate expects DomT as first argument, got {domT}")
        if not isinstance(funT, irT.ArrowT):
            raise TypeError(f"Tabulate expects ArrowT as second argument, got {funT}")
        if funT.argT != domT.carT:
            raise TypeError(f"Tabulate function argument type {funT.argT} does not match domain carrier type {domT.carT}")
        return irT.FuncT(domT, funT.resT)

    @handles(ir.DomOf)
    def _(self, node: ir.DomOf):
        funcT, = self.visit_children(node)
        if not isinstance(funcT, irT.FuncT):
            raise TypeError(f"DomOf expects FuncT, got {funcT}")
        return funcT.domT

    @handles(ir.ImageOf)
    def _(self, node: ir.ImageOf):
        funcT, = self.visit_children(node)
        if not isinstance(funcT, irT.FuncT):
            raise TypeError(f"ImageOf expects FuncT, got {funcT}")
        # TODO: Verify image domain construction
        # The image domain should have the result type as carrier and appropriate capabilities
        return irT.DomT(funcT.resT, funcT.domT.cap)

    @handles(ir.Apply)
    def _(self, node: ir.Apply):
        funcT, argT = self.visit_children(node)
        if not isinstance(funcT, irT.FuncT):
            raise TypeError(f"Apply expects FuncT as first argument, got {funcT}")
        if argT != funcT.domT.carT:
            raise TypeError(f"Apply argument type {argT} does not match function domain carrier type {funcT.domT.carT}")
        return funcT.resT

    @handles(ir.ListLit)
    def _(self, node: ir.ListLit):
        childTs = self.visit_children(node)
        if len(childTs) == 0:
            raise NotImplementedError("Cannot infer type of empty list literal")
        elemT = childTs[0]
        for i, childT in enumerate(childTs[1:], 1):
            if childT != elemT:
                raise TypeError(f"ListLit has heterogeneous elements: element 0 is {elemT}, element {i} is {childT}")
        # List[B] is Func(Fin(n) -> B)
        # TODO: Verify list domain construction
        n = len(childTs)
        finDom = irT.DomT(irT.Int, irT.DomCap(finite=True, enumerable=1, ordered=True))
        return irT.FuncT(finDom, elemT)

    @handles(ir.Fold)
    def _(self, node: ir.Fold):
        funcT, funT, initT = self.visit_children(node)
        if not isinstance(funcT, irT.FuncT):
            raise TypeError(f"Fold expects FuncT as first argument, got {funcT}")
        if not isinstance(funT, irT.ArrowT):
            raise TypeError(f"Fold expects ArrowT as second argument, got {funT}")
        # Fold signature: Seq[A] -> ((A,B) -> B) -> B -> B
        # So fun should be (elemT, resT) -> resT
        elemT = funcT.resT
        resT = funT.resT
        if initT != resT:
            raise TypeError(f"Fold init type {initT} does not match function result type {resT}")
        expectedFunT = irT.ArrowT(irT.TupleT(elemT, resT), resT)
        if funT != expectedFunT:
            raise TypeError(f"Fold function type {funT} does not match expected type ArrowT(TupleT({elemT}, {resT}), {resT})")
        return resT

    ##############################
    ## Surface-level IR nodes (Used for analysis, but can be collapsed)
    ##############################

    @handles(ir.And)
    def _(self, node: ir.And):
        leftT, rightT = self.visit_children(node)
        if leftT != irT.Bool or rightT != irT.Bool:
            raise TypeError(f"And expects Bool operands, got {leftT} and {rightT}")
        return irT.Bool

    @handles(ir.Implies)
    def _(self, node: ir.Implies):
        leftT, rightT = self.visit_children(node)
        if leftT != irT.Bool or rightT != irT.Bool:
            raise TypeError(f"Implies expects Bool operands, got {leftT} and {rightT}")
        return irT.Bool

    @handles(ir.Or)
    def _(self, node: ir.Or):
        leftT, rightT = self.visit_children(node)
        if leftT != irT.Bool or rightT != irT.Bool:
            raise TypeError(f"Or expects Bool operands, got {leftT} and {rightT}")
        return irT.Bool

    @handles(ir.Add)
    def _(self, node: ir.Add):
        leftT, rightT = self.visit_children(node)
        if leftT != irT.Int or rightT != irT.Int:
            raise TypeError(f"Add expects Int operands, got {leftT} and {rightT}")
        return irT.Int

    @handles(ir.Sub)
    def _(self, node: ir.Sub):
        leftT, rightT = self.visit_children(node)
        if leftT != irT.Int or rightT != irT.Int:
            raise TypeError(f"Sub expects Int operands, got {leftT} and {rightT}")
        return irT.Int

    @handles(ir.Mul)
    def _(self, node: ir.Mul):
        leftT, rightT = self.visit_children(node)
        if leftT != irT.Int or rightT != irT.Int:
            raise TypeError(f"Mul expects Int operands, got {leftT} and {rightT}")
        return irT.Int

    @handles(ir.Gt)
    def _(self, node: ir.Gt):
        leftT, rightT = self.visit_children(node)
        if leftT != irT.Int or rightT != irT.Int:
            raise TypeError(f"Gt expects Int operands, got {leftT} and {rightT}")
        return irT.Bool

    @handles(ir.GtEq)
    def _(self, node: ir.GtEq):
        leftT, rightT = self.visit_children(node)
        if leftT != irT.Int or rightT != irT.Int:
            raise TypeError(f"GtEq expects Int operands, got {leftT} and {rightT}")
        return irT.Bool

    @handles(ir.Windows)
    def _(self, node: ir.Windows):
        listT, sizeT, strideT = self.visit_children(node)
        if not isinstance(listT, irT.FuncT):
            raise TypeError(f"Windows expects FuncT as first argument, got {listT}")
        if sizeT != irT.Int or strideT != irT.Int:
            raise TypeError(f"Windows expects Int for size and stride, got {sizeT} and {strideT}")
        # Windows: SeqDom[A] -> Int -> Int -> Func[Fin(n) -> SeqDom[A]]
        # Returns a function from finite domain to sequences
        elemT = listT.resT
        # TODO: Verify window domain construction
        windowSizeDom = irT.DomT(irT.Int, irT.DomCap(finite=True, enumerable=1, ordered=True))
        windowSeqT = irT.FuncT(listT.domT, elemT)
        nWindowsDom = irT.DomT(irT.Int, irT.DomCap(finite=True, enumerable=1, ordered=True))
        return irT.FuncT(nWindowsDom, windowSeqT)

    @handles(ir.Tiles)
    def _(self, node: ir.Tiles):
        gridT, size_rT, size_cT, stride_rT, stride_cT = self.visit_children(node)
        if not isinstance(gridT, irT.FuncT):
            raise TypeError(f"Tiles expects FuncT as first argument, got {gridT}")
        for name, sT in [("size_r", size_rT), ("size_c", size_cT), ("stride_r", stride_rT), ("stride_c", stride_cT)]:
            if sT != irT.Int:
                raise TypeError(f"Tiles {name} must be Int, got {sT}")
        # Tiles: GridDom[A] -> int -> int -> int -> int -> Func[Fin(r) x Fin(c) -> GridDom[A]]
        # TODO: Verify tiles domain construction
        elemT = gridT.resT
        tileDom = gridT.domT  # TODO: This should be the tile domain
        nTilesDom = irT.DomT(irT.Int, irT.DomCap(finite=True, enumerable=1, ordered=True))
        tileGridT = irT.FuncT(tileDom, elemT)
        return irT.FuncT(nTilesDom, tileGridT)

    @handles(ir.SumReduce)
    def _(self, node: ir.SumReduce):
        funcT, = self.visit_children(node)
        if not isinstance(funcT, irT.FuncT):
            raise TypeError(f"SumReduce expects FuncT, got {funcT}")
        if funcT.resT != irT.Int:
            raise TypeError(f"SumReduce expects FuncT with Int element type, got {funcT.resT}")
        return irT.Int

    @handles(ir.ProdReduce)
    def _(self, node: ir.ProdReduce):
        funcT, = self.visit_children(node)
        if not isinstance(funcT, irT.FuncT):
            raise TypeError(f"ProdReduce expects FuncT, got {funcT}")
        if funcT.resT != irT.Int:
            raise TypeError(f"ProdReduce expects FuncT with Int element type, got {funcT.resT}")
        return irT.Int

    @handles(ir.Distinct)
    def _(self, node: ir.Distinct):
        funcT, = self.visit_children(node)
        if not isinstance(funcT, irT.FuncT):
            raise TypeError(f"Distinct expects FuncT, got {funcT}")
        return irT.Bool
