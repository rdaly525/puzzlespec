from __future__ import annotations

from ..pass_base import Context, AnalysisObject, Analysis, handles
from ..envobj import EnvsObj, TypeEnv
from ...dsl import ir
import typing as tp

def _is_domain(node: ir.Value) -> bool:
    return isinstance(node, ir.Value) and isinstance(node.T, ir.DomT)

class TypeCheckResult(AnalysisObject):
    def __init__(self, Tmap: tp.Dict[ir.Node, ir.Type]):
        self.Tmap = Tmap

# This class Verifies that the IR is well-typed. This includes the Types themselves
class TypeCheckingPass(Analysis):
    requires = (EnvsObj,)
    produces = ()
    name = "type_checking"
    
    def __init__(self):
        super().__init__()

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.tenv: TypeEnv = ctx.get(EnvsObj).tenv
        self.bctx: tp.List[ir.Type] = []
        self.visit(root)
        return TypeCheckResult(self._cache)

    ##############################
    ## Core-level IR Type nodes 
    ##############################

    @handles(ir.UnitT)
    def _(self, node: ir.UnitT):
        # UnitT has no children, nothing to check
        return node

    @handles(ir.BoolT)
    def _(self, node: ir.BoolT):
        # BoolT has no children, nothing to check
        return node

    @handles(ir.IntT)
    def _(self, node: ir.IntT):
        # IntT has no children, nothing to check
        return node

    @handles(ir.EnumT)
    def _(self, node: ir.EnumT):
        # EnumT has no children, nothing to check
        return node

    @handles(ir.TupleT)
    def _(self, node: ir.TupleT):
        # Visit children to verify they are Types
        childTs = self.visit_children(node)
        if not all(isinstance(childT, ir.Type) for childT in childTs):
            raise TypeError(f"TupleT children must be Types, got {childTs}")
        return node

    @handles(ir.SumT)
    def _(self, node: ir.SumT):
        # Visit children to verify they are Types
        childTs = self.visit_children(node)
        if not all(isinstance(childT, ir.Type) for childT in childTs):
            raise TypeError(f"SumT children must be Types, got {childTs}")
        return node

    @handles(ir.ArrowT)
    def _(self, node: ir.ArrowT):
        # Visit children to verify they are Types
        argT, resT = self.visit_children(node)
        if not isinstance(argT, ir.Type):
            raise TypeError(f"ArrowT argument must be a Type, got {argT}")
        if not isinstance(resT, ir.Type):
            raise TypeError(f"ArrowT result must be a Type, got {resT}")
        return node

    @handles(ir.DomT)
    def _(self, node: ir.DomT):
        # Visit children to verify they are Types
        factorTs = self.visit_children(node)
        if not all(isinstance(factorT, ir.Type) for factorT in factorTs):
            raise TypeError(f"DomT factors must be Types, got {factorTs}")
        return node

    @handles(ir.FuncT)
    def _(self, node: ir.FuncT):
        # Visit children
        domT, retT = self.visit_children(node)
        # Verify domain is a Value with DomT type
        if not isinstance(node.dom, ir.Value):
            raise TypeError(f"FuncT domain must be a Value, got {node.dom}")
        if not isinstance(domT, ir.DomT):
            raise TypeError(f"FuncT domain must have DomT type, got {domT}")
        # Verify result is a Type
        if not isinstance(retT, ir.Type):
            raise TypeError(f"FuncT result must be a Type, got {retT}")
        return node

    ##############################
    ## Core-level IR Value nodes (Used throughout entire compiler flow)
    ##############################

    @handles(ir.VarRef)
    def _(self, node: ir.VarRef):
        # VarRef has no children, just verify it's in the type environment
        if node.sid not in self.tenv:
            raise TypeError(f"Variable with sid={node.sid} not found in type environment")
        # Return the type from the environment
        return self.tenv[node.sid]

    @handles(ir.BoundVar)
    def _(self, node: ir.BoundVar):
        # BoundVar has no children, just verify the index is valid
        if node.idx >= len(self.bctx):
            raise TypeError(f"BoundVar index {node.idx} out of bounds (bctx length: {len(self.bctx)})")
        # Return the type from the bound context
        return self.bctx[-(node.idx+1)]

    @handles(ir.Unit)
    def _(self, node: ir.Unit):
        # Visit children (just the type)
        self.visit_children(node)
        # Verify type is UnitT
        if not isinstance(node.T, ir.UnitT):
            raise TypeError(f"Unit must have UnitT type, got {node.T}")
        return node.T

    @handles(ir.Lambda)
    def _(self, node: ir.Lambda):
        # Verify type is ArrowT
        if not isinstance(node.T, ir.ArrowT):
            raise TypeError(f"Lambda must have ArrowT type, got {node.T}")
        # Verify body is a Value
        body = node._children[1]  # Skip type at index 0
        if not isinstance(body, ir.Value):
            raise TypeError(f"Lambda body must be a Value, got {body}")
        # Push parameter type onto bound context for body checking
        self.bctx.append(node.T.argT)
        # Visit body and get its type
        bodyT = self.visit(body)
        # Pop bound context
        self.bctx.pop()
        # Verify body type matches ArrowT result type
        if not bodyT.eq(node.T.resT):
            raise TypeError(f"Lambda body type {bodyT} does not match ArrowT result type {node.T.resT}")
        return node.T

    @handles(ir.Lit)
    def _(self, node: ir.Lit):
        # Visit children (just the type)
        self.visit_children(node)
        # Verify type matches the literal value
        # The type should be one of the base types
        if not isinstance(node.T, (ir.BoolT, ir.IntT, ir.EnumT)):
            raise TypeError(f"Lit must have BoolT, IntT, or EnumT type, got {node.T}")
        return node.T

    @handles(ir.Eq)
    def _(self, node: ir.Eq):
        # Visit children and get their types (skip first child which is the type)
        _, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"Eq must have BoolT type, got {node.T}")
        # Verify operands have same type
        if not aT.eq(bT):
            raise TypeError(f"Eq has operands of inconsistent types: {aT} != {bT}")
        return node.T

    @handles(ir.Lt)
    def _(self, node: ir.Lt):
        # Visit children and get their types (skip first child which is the type)
        _, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"Lt must have BoolT type, got {node.T}")
        # Verify operands are Int
        if not isinstance(aT, ir.IntT) or not isinstance(bT, ir.IntT):
            raise TypeError(f"Lt expects Int operands, got {aT} and {bT}")
        return node.T

    @handles(ir.LtEq)
    def _(self, node: ir.LtEq):
        # Visit children and get their types (skip first child which is the type)
        _, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"LtEq must have BoolT type, got {node.T}")
        # Verify operands are Int
        if not isinstance(aT, ir.IntT) or not isinstance(bT, ir.IntT):
            raise TypeError(f"LtEq expects Int operands, got {aT} and {bT}")
        return node.T

    @handles(ir.Ite)
    def _(self, node: ir.Ite):
        # Visit children and get their types (skip first child which is the type)
        _, predT, tT, fT = self.visit_children(node)
        # Verify predicate is Bool
        if not isinstance(predT, ir.BoolT):
            raise TypeError(f"Ite predicate must be Bool, got {predT}")
        # Verify branches have same type
        if not tT.eq(fT):
            raise TypeError(f"Ite branches must have same type: {tT} != {fT}")
        # Verify result type matches branch type
        if not node.T.eq(tT):
            raise TypeError(f"Ite result type {node.T} does not match branch type {tT}")
        return node.T

    @handles(ir.Not)
    def _(self, node: ir.Not):
        # Visit children and get their types (skip first child which is the type)
        _, aT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"Not must have BoolT type, got {node.T}")
        # Verify operand is Bool
        if not isinstance(aT, ir.BoolT):
            raise TypeError(f"Not expects Bool operand, got {aT}")
        return node.T

    @handles(ir.Neg)
    def _(self, node: ir.Neg):
        # Visit children and get their types (skip first child which is the type)
        _, aT = self.visit_children(node)
        # Verify type is IntT
        if not isinstance(node.T, ir.IntT):
            raise TypeError(f"Neg must have IntT type, got {node.T}")
        # Verify operand is Int
        if not isinstance(aT, ir.IntT):
            raise TypeError(f"Neg expects Int operand, got {aT}")
        return node.T

    @handles(ir.Div)
    def _(self, node: ir.Div):
        # Visit children and get their types (skip first child which is the type)
        _, aT, bT = self.visit_children(node)
        # Verify type is IntT
        if not isinstance(node.T, ir.IntT):
            raise TypeError(f"Div must have IntT type, got {node.T}")
        # Verify operands are Int
        if not isinstance(aT, ir.IntT) or not isinstance(bT, ir.IntT):
            raise TypeError(f"Div expects Int operands, got {aT} and {bT}")
        return node.T

    @handles(ir.Mod)
    def _(self, node: ir.Mod):
        # Visit children and get their types (skip first child which is the type)
        _, aT, bT = self.visit_children(node)
        # Verify type is IntT
        if not isinstance(node.T, ir.IntT):
            raise TypeError(f"Mod must have IntT type, got {node.T}")
        # Verify operands are Int
        if not isinstance(aT, ir.IntT) or not isinstance(bT, ir.IntT):
            raise TypeError(f"Mod expects Int operands, got {aT} and {bT}")
        return node.T

    @handles(ir.Conj)
    def _(self, node: ir.Conj):
        # Visit children and get their types (skip first child which is the type)
        childTs = self.visit_children(node)[1:]
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"Conj must have BoolT type, got {node.T}")
        # Verify all operands are Bool
        for i, childT in enumerate(childTs):
            if not isinstance(childT, ir.BoolT):
                raise TypeError(f"Conj child {i} must be Bool, got {childT}")
        return node.T

    @handles(ir.Disj)
    def _(self, node: ir.Disj):
        # Visit children and get their types (skip first child which is the type)
        childTs = self.visit_children(node)[1:]
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"Disj must have BoolT type, got {node.T}")
        # Verify all operands are Bool
        for i, childT in enumerate(childTs):
            if not isinstance(childT, ir.BoolT):
                raise TypeError(f"Disj child {i} must be Bool, got {childT}")
        return node.T

    @handles(ir.Sum)
    def _(self, node: ir.Sum):
        # Visit children and get their types (skip first child which is the type)
        childTs = self.visit_children(node)[1:]
        # Verify type is IntT
        if not isinstance(node.T, ir.IntT):
            raise TypeError(f"Sum must have IntT type, got {node.T}")
        # Verify all operands are Int
        for i, childT in enumerate(childTs):
            if not isinstance(childT, ir.IntT):
                raise TypeError(f"Sum child {i} must be Int, got {childT}")
        return node.T

    @handles(ir.Prod)
    def _(self, node: ir.Prod):
        # Visit children and get their types (skip first child which is the type)
        childTs = self.visit_children(node)[1:]
        # Verify type is IntT
        if not isinstance(node.T, ir.IntT):
            raise TypeError(f"Prod must have IntT type, got {node.T}")
        # Verify all operands are Int
        for i, childT in enumerate(childTs):
            if not isinstance(childT, ir.IntT):
                raise TypeError(f"Prod child {i} must be Int, got {childT}")
        return node.T

    @handles(ir.Universe)
    def _(self, node: ir.Universe):
        # Visit children (just the type)
        self.visit_children(node)
        # Verify type is DomT
        if not isinstance(node.T, ir.DomT):
            raise TypeError(f"Universe must have DomT type, got {node.T}")
        return node.T

    @handles(ir.Fin)
    def _(self, node: ir.Fin):
        # Visit children and get their types (skip first child which is the type)
        _, NT = self.visit_children(node)
        # Verify type is DomT
        if not isinstance(node.T, ir.DomT):
            raise TypeError(f"Fin must have DomT type, got {node.T}")
        # Verify N argument is Int
        if not isinstance(NT, ir.IntT):
            raise TypeError(f"Fin expects Int argument, got {NT}")
        if node.T.rank != 1 or node.T.axes[0] != 0:
            raise TypeError(f"Fin domain must be rank 1, got {node.T.axes}")        
        if not node.T.fin:
            raise TypeError(f"Fin domain must be finite, got {node.T.fins}")
        if not node.T.ord:
            raise TypeError(f"Fin domain must be ordered, got {node.T.ords}")
        if not NT.eq(node.T.carT):
            raise TypeError(f"Fin argument {NT} does not match domain carrier type {node.T.carT}")
        return node.T

    @handles(ir.EnumLit)
    def _(self, node: ir.EnumLit):
        # Visit children (just the type)
        self.visit_children(node)
        # Verify type is EnumT
        if not isinstance(node.T, ir.EnumT):
            raise TypeError(f"EnumLit must have EnumT type, got {node.T}")
        # Verify label is in the enum
        if node.label not in node.T.labels:
            raise TypeError(f"EnumLit label '{node.label}' not in enum labels {node.T.labels}")
        return node.T

    @handles(ir.Card)
    def _(self, node: ir.Card):
        # Visit children and get their types (skip first child which is the type)
        _, domainT = self.visit_children(node)
        # Verify type is IntT
        if not isinstance(node.T, ir.IntT):
            raise TypeError(f"Card must have IntT type, got {node.T}")
        # Verify domain argument is a domain
        if not isinstance(domainT, ir.DomT):
            raise TypeError(f"Card expects domain argument, got {domainT}")
        if not domainT.fin:
            raise TypeError(f"Card expects finite domain, got {domainT}")
        return node.T

    @handles(ir.IsMember)
    def _(self, node: ir.IsMember):
        # Visit children and get their types (skip first child which is the type)
        _, domainT, valT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"IsMember must have BoolT type, got {node.T}")
        # Verify domain argument is a domain
        if not isinstance(domainT, ir.DomT):
            raise TypeError(f"IsMember expects domain argument, got {domainT}")
        # Verify value argument type matches domain carrier type
        if not valT.eq(domainT.carT):
            raise TypeError(f"IsMember value type {valT} does not match domain carrier type {domainT.carT}")
        return node.T

    @handles(ir.CartProd)
    def _(self, node: ir.CartProd):
        # Visit children and get their types (skip first child which is the type)
        domTs = self.visit_children(node)[1:]
        # Verify type is DomT
        if not isinstance(node.T, ir.DomT):
            raise TypeError(f"CartProd must have DomT type, got {node.T}")
        # Verify all arguments are domains
        for i, domT in enumerate(domTs):
            if not isinstance(domT, ir.DomT):
                raise TypeError(f"CartProd argument {i} must be a domain, got {domT}")
        for i, (domT, T) in enumerate(zip(domTs, node.T.factors)):
            if not domT.carT.eq(T):
                raise TypeError(f"CartProd argument {i} type {domT.carT} does not match domain factor type {T}")
        return node.T

    @handles(ir.DomProj)
    def _(self, node: ir.DomProj):
        # Visit children and get their types (skip first child which is the type)
        _, domT = self.visit_children(node)
        # Verify type is DomT
        if not isinstance(node.T, ir.DomT):
            raise TypeError(f"DomProj must have DomT type, got {node.T}")
        # Verify domain argument is a domain
        if not isinstance(domT, ir.DomT):
            raise TypeError(f"DomProj expects domain argument, got {domT}")
        if node.idx >= len(domT.factors):
            raise TypeError(f"DomProj index {node.idx} out of bounds for tuple of length {len(domT.carT.elemTs)}")
        if not node.T.carT.eq(domT.factors[node.idx]):
            raise TypeError(f"DomProj result type {node.T} does not match domain factor type {domT.factors[node.idx]}")
        if node.T.fin != domT.fins[node.idx]:
            raise TypeError(f"DomProj result domain must be finite, got {node.T.fin}")
        if node.T.ord != domT.ords[node.idx]:
            raise TypeError(f"DomProj result domain must be ordered, got {node.T.ord}")
        return node.T

    @handles(ir.TupleLit)
    def _(self, node: ir.TupleLit):
        # Visit children and get their types (skip first child which is the type)
        valTs = self.visit_children(node)[1:]
        # Verify type is TupleT
        if not isinstance(node.T, ir.TupleT):
            raise TypeError(f"TupleLit must have TupleT type, got {node.T}")
        # Verify all value arguments match tuple element types
        if len(valTs) != len(node.T.elemTs):
            raise TypeError(f"TupleLit has {len(valTs)} values ({valTs}) but type has {len(node.T.elemTs)} elements ({node.T.elemTs})")
        for i, (valT, elemT) in enumerate(zip(valTs, node.T.elemTs)):
            if not valT.eq(elemT):
                raise TypeError(f"TupleLit value {i} type {valT} does not match tuple element type {elemT}")
        return node.T

    @handles(ir.Proj)
    def _(self, node: ir.Proj):
        # Visit children and get their types (skip first child which is the type)
        _, tupT = self.visit_children(node)
        # Verify tuple argument is a Value with TupleT type
        if not isinstance(tupT, ir.TupleT):
            raise TypeError(f"Proj expects tuple argument, got {tupT}")
        if node.idx >= len(tupT.elemTs):
            raise TypeError(f"Proj index {node.idx} out of bounds for tuple of length {len(tupT.elemTs)}")
        # Verify result type matches projected element type
        if not node.T.eq(tupT.elemTs[node.idx]):
            raise TypeError(f"Proj result type {node.T} does not match tuple element type {tupT.elemTs[node.idx]}")
        return node.T

    @handles(ir.DisjUnion)
    def _(self, node: ir.DisjUnion):
        # Visit children and get their types (skip first child which is the type)
        domTs = self.visit_children(node)[1:]
        # Verify type is DomT
        if not isinstance(node.T, ir.DomT):
            raise TypeError(f"DisjUnion must have DomT type, got {node.T}")
        # Verify all arguments are domains
        for i, domT in enumerate(domTs):
            if not isinstance(domT, ir.DomT):
                raise TypeError(f"DisjUnion argument {i} must be a domain, got {domT}")
        if not isinstance(node.T.carT, ir.SumT):
            raise TypeError(f"DisjUnion must have sum carrier type, got {node.T.carT}")
        return node.T

    @handles(ir.DomInj)
    def _(self, node: ir.DomInj):
        # Visit children and get their types (skip first child which is the type)
        _, domT = self.visit_children(node)
        # Verify type is DomT
        if not isinstance(node.T, ir.DomT):
            raise TypeError(f"DomInj must have DomT type, got {node.T}")
        # Verify domain argument is a domain
        if not isinstance(domT, ir.DomT):
            raise TypeError(f"DomInj expects domain argument, got {domT}")
        if not isinstance(domT.carT, ir.SumT):
            raise TypeError(f"DomInj expects sum carrier type, got {domT.carT}")
        if node.idx >= len(domT.carT.elemTs):
            raise TypeError(f"DomInj index {node.idx} out of bounds for sum of length {len(domT.carT.elemTs)}")
        if not node.T.eq(domT.carT.elemTs[node.idx]):
            raise TypeError(f"DomInj result type {node.T} does not match sum element type {domT.carT.elemTs[node.idx]}")
        return node.T

    @handles(ir.Inj)
    def _(self, node: ir.Inj):
        # Visit children and get their types (skip first child which is the type)
        _, valT = self.visit_children(node)
        if not isinstance(node.T, ir.SumT):
            raise TypeError(f"Inj must have SumT type, got {node.T}")
        if node.idx >= len(node.T.elemTs):
            raise TypeError(f"Inj index {node.idx} out of bounds for sum of length {len(node.T.elemTs)}")
        if not valT.eq(node.T.elemTs[node.idx]):
            raise TypeError(f"Inj value type {valT} does not match sum element type {node.T.elemTs[node.idx]}")
        return node.T

    @handles(ir.Match)
    def _(self, node: ir.Match):
        # Visit children and get their types (skip first child which is the type)
        _, scrutT, branchesT = self.visit_children(node)
        # Verify scrutinee is a Value with SumT type
        if not isinstance(scrutT, ir.SumT):
            raise TypeError(f"Match scrutinee must be SumT, got {scrutT}")
        # Verify branches is a Value with TupleT type
        if not isinstance(branchesT, ir.TupleT):
            raise TypeError(f"Match branches must be TupleT, got {branchesT}")
        if len(branchesT.elemTs) != len(scrutT.elemTs):
            raise TypeError(f"Match branches count {len(branchesT.elemTs)} does not match sum type count {len(scrutT.elemTs)}")
        # TODO: Verify each branch is an ArrowT matching the corresponding sum component
        # Verify result type matches all branch result types
        # For now, just verify branches is a tuple of appropriate length
        for i, (sum_elem_T, branch_T) in enumerate(zip(scrutT.elemTs, branchesT.elemTs)):
            if not isinstance(branch_T, ir.ArrowT):
                raise TypeError(f"Match branch {i} must be ArrowT, got {branch_T}")
            if not branch_T.argT.eq(sum_elem_T):
                raise TypeError(f"Match branch {i} argument type {branch_T.argT} does not match sum component {sum_elem_T}")
            if not branch_T.resT.eq(node.T):
                raise TypeError(f"Match branch {i} result type {branch_T.resT} does not match match result type {node.T}")
        return node.T

    @handles(ir.Restrict)
    def _(self, node: ir.Restrict):
        # Visit children and get their types (skip first child which is the type)
        _, domainT, predT = self.visit_children(node)
        # Verify type is DomT
        if not isinstance(node.T, ir.DomT):
            raise TypeError(f"Restrict must have DomT type, got {node.T}")
        # Verify domain argument is a domain
        if not isinstance(domainT, ir.DomT):
            raise TypeError(f"Restrict expects domain argument, got {domainT}")
        # Verify predicate is a Value with ArrowT type
        if not isinstance(predT, ir.ArrowT):
            raise TypeError(f"Restrict expects ArrowT predicate, got {predT}")
        if not predT.argT.eq(domainT.carT):
            raise TypeError(f"Restrict predicate argument type {predT.argT} does not match domain carrier type {domainT.carT}")
        if not isinstance(predT.resT, ir.BoolT):
            raise TypeError(f"Restrict predicate must return Bool, got {predT.resT}")
        if not node.T.carT.eq(domainT.carT):
            raise TypeError(f"Restrict result carrier type {node.T.carT} does not match domain carrier type {domainT.carT}")
        return node.T

    @handles(ir.Forall)
    def _(self, node: ir.Forall):
        # Visit children and get their types (skip first child which is the type)
        _, domainT, funT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"Forall must have BoolT type, got {node.T}")
        # Verify domain argument is a domain
        if not isinstance(domainT, ir.DomT):
            raise TypeError(f"Forall expects domain argument, got {domainT}")
        # Verify function is a Value with ArrowT type
        if not isinstance(funT, ir.ArrowT):
            raise TypeError(f"Forall expects ArrowT function, got {funT}")
        if not funT.argT.eq(domainT.carT):
            raise TypeError(f"Forall function argument type {funT.argT} does not match domain carrier type {domainT.carT}")
        if not isinstance(funT.resT, ir.BoolT):
            raise TypeError(f"Forall function must return Bool, got {funT.resT}")
        return node.T

    @handles(ir.Exists)
    def _(self, node: ir.Exists):
        # Visit children and get their types (skip first child which is the type)
        _, domainT, funT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"Exists must have BoolT type, got {node.T}")
        # Verify domain argument is a domain
        if not isinstance(domainT, ir.DomT):
            raise TypeError(f"Exists expects domain argument, got {domainT}")
        # Verify function is a Value with ArrowT type
        if not isinstance(funT, ir.ArrowT):
            raise TypeError(f"Exists expects ArrowT function, got {funT}")
        if not funT.argT.eq(domainT.carT):
            raise TypeError(f"Exists function argument type {funT.argT} does not match domain carrier type {domainT.carT}")
        if not isinstance(funT.resT, ir.BoolT):
            raise TypeError(f"Exists function must return Bool, got {funT.resT}")
        return node.T

    @handles(ir.Map)
    def _(self, node: ir.Map):
        # Visit children and get their types (skip first child which is the type)
        _, domT, funT = self.visit_children(node)
        # Verify type is FuncT
        if not isinstance(node.T, ir.FuncT):
            raise TypeError(f"Map must have FuncT type, got {node.T}")
        # Verify domain argument is a domain
        if not isinstance(domT, ir.DomT):
            raise TypeError(f"Map expects domain argument, got {domT}")
        # Verify function is a Value with ArrowT type
        if not isinstance(funT, ir.ArrowT):
            raise TypeError(f"Map expects ArrowT function, got {funT}")
        if not funT.argT.eq(domT.carT):
            raise TypeError(f"Map function argument type {funT.argT} does not match domain carrier type {domT.carT}")
        if not node.T.retT.eq(funT.resT):
            raise TypeError(f"Map result type {node.T.retT} does not match function result type {funT.resT}")
        return node.T

    @handles(ir.Image)
    def _(self, node: ir.Image):
        # Visit children and get their types (skip first child which is the type)
        _, funcT = self.visit_children(node)
        # Verify type is DomT
        if not isinstance(node.T, ir.DomT):
            raise TypeError(f"Image must have DomT type, got {node.T}")
        # Verify function argument is a Value with FuncT type
        if not isinstance(funcT, ir.FuncT):
            raise TypeError(f"Image expects FuncT argument, got {funcT}")
        if not node.T.eq(funcT.retT):
            raise TypeError(f"Image result type {node.T} does not match function result type {funcT.retT}")
        return node.T

    @handles(ir.Apply)
    def _(self, node: ir.Apply):
        # Visit children and get their types (skip first child which is the type)
        _, funcT, argT = self.visit_children(node)
        # Verify function argument is a Value with FuncT type
        if not isinstance(funcT, ir.FuncT):
            raise TypeError(f"Apply expects FuncT function, got {funcT}")
        # Verify argument type matches function domain carrier type
        if not argT.eq(funcT.dom.T.carT):
            raise TypeError(f"Apply argument type {argT} does not match function domain carrier type {funcT.dom.carT}")
        # Verify result type matches function result type
        if not node.T.eq(funcT.retT):
            raise TypeError(f"Apply result type {node.T} does not match function result type {funcT.retT}")
        return node.T

    @handles(ir.ListLit)
    def _(self, node: ir.ListLit):
        # Visit children and get their types (skip first child which is the type)
        valTs = self.visit_children(node)[1:]
        # Verify type is FuncT
        if not isinstance(node.T, ir.FuncT):
            raise TypeError(f"ListLit must have FuncT type, got {node.T}")
        # Verify all value arguments have same type
        if len(valTs) == 0:
            raise NotImplementedError("Cannot type check empty list literal")
        elemT = valTs[0]
        for i, valT in enumerate(valTs[1:], 1):
            if not valT.eq(elemT):
                raise TypeError(f"ListLit has heterogeneous elements: element 0 is {elemT}, element {i} is {valT}")
        # TODO: Verify list domain construction matches FuncT
        if not isinstance(node.T, ir.FuncT):
            raise TypeError(f"ListLit must have FuncT type, got {node.T}")
        if not node.T.retT.eq(elemT):
            raise TypeError(f"ListLit result type {node.T.retT} does not match element type {elemT}")
        if not node.T.dom.T.eq(ir.DomT.make(ir.IntT(), True, True)):
            raise TypeError(f"ListLit domain type {node.T.dom.T} does not match expected type {ir.DomT.make(ir.IntT(), True, True)}")
        return node.T

    @handles(ir.Fold)
    def _(self, node: ir.Fold):
        # Visit children and get their types (skip first child which is the type)
        _, funcT, funT, initT = self.visit_children(node)
        # Verify function argument is a Value with FuncT type
        if not isinstance(funcT, ir.FuncT):
            raise TypeError(f"Fold expects FuncT function, got {funcT}")
        # Verify fun argument is a Value with ArrowT type
        if not isinstance(funT, ir.ArrowT):
            raise TypeError(f"Fold expects ArrowT fun, got {funT}")
        # Fold signature: Seq[A] -> ((A,B) -> B) -> B -> B
        # So fun should be (elemT, resT) -> resT
        elemT = funcT.retT
        resT = funT.resT
        if not initT.eq(resT):
            raise TypeError(f"Fold init type {initT} does not match function result type {resT}")
        expectedFunT = ir.ArrowT(ir.TupleT(elemT, resT), resT)
        if not funT.eq(expectedFunT):
            raise TypeError(f"Fold function type {funT} does not match expected type {expectedFunT}")
        # Verify result type matches
        if not node.T.eq(resT):
            raise TypeError(f"Fold result type {node.T} does not match expected type {resT}")
        return node.T

    @handles(ir.Slice)
    def _(self, node: ir.Slice):
        # Visit children and get their types (skip first child which is the type)
        _, domT, loT, hiT = self.visit_children(node)
        # Verify type is DomT
        if not isinstance(node.T, ir.DomT):
            raise TypeError(f"Slice must have DomT type, got {node.T}")
        # Verify domain argument is a domain
        if not isinstance(domT, ir.DomT):
            raise TypeError(f"Slice expects domain argument, got {domT}")
        # Verify lo and hi are Int
        if not isinstance(loT, ir.IntT):
            raise TypeError(f"Slice lo must be Int, got {loT}")
        if not isinstance(hiT, ir.IntT):
            raise TypeError(f"Slice hi must be Int, got {hiT}")
        if not node.T.eq(domT):
            raise TypeError(f"Slice result type {node.T} does not match domain carrier type {domT}")
        return node.T

    @handles(ir.Index)
    def _(self, node: ir.Index):
        # Visit children and get their types (skip first child which is the type)
        _, domT, idxT = self.visit_children(node)
        # Verify domain argument is a domain
        if not isinstance(domT, ir.DomT):
            raise TypeError(f"Index expects domain argument, got {domT}")
        if not idxT.eq(domT.carT):
            raise TypeError(f"Index idx type {idxT} does not match domain carrier type {domT.carT}")
        # Index only works on rank 1 domains
        if domT.rank != 1:
            raise TypeError(f"Index only works on rank 1 domains, got {domT.rank}")
        if not isinstance(node.T, ir.DomT):
            raise TypeError(f"Index result type {node.T} must be a domain, got {node.T}")
        if not node.T.carT.eq(domT.factors[domT.axes[0]]):
            raise TypeError(f"Index result domain factor type {node.T.carT} does not match domain factor type {domT.factors[domT.axes[0]]}")
        if node.T.fin != domT.fins[domT.axes[0]]:
            raise TypeError(f"Slice result domain must be finite, got {node.T.fin}")
        if node.T.ord != domT.ords[domT.axes[0]]:
            raise TypeError(f"Slice result domain must be ordered, got {node.T.ord}")
        return node.T

    ##############################
    ## Surface-level IR nodes (Used for analysis, but can be collapsed)
    ##############################

    @handles(ir.And)
    def _(self, node: ir.And):
        # Visit children and get their types (skip first child which is the type)
        _, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"And must have BoolT type, got {node.T}")
        # Verify operands are Bool
        if not isinstance(aT, ir.BoolT):
            raise TypeError(f"And operand a must be Bool, got {aT}")
        if not isinstance(bT, ir.BoolT):
            raise TypeError(f"And operand b must be Bool, got {bT}")
        return node.T

    @handles(ir.Implies)
    def _(self, node: ir.Implies):
        # Visit children and get their types (skip first child which is the type)
        _, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"Implies must have BoolT type, got {node.T}")
        # Verify operands are Bool
        if not isinstance(aT, ir.BoolT):
            raise TypeError(f"Implies operand a must be Bool, got {aT}")
        if not isinstance(bT, ir.BoolT):
            raise TypeError(f"Implies operand b must be Bool, got {bT}")
        return node.T

    @handles(ir.Or)
    def _(self, node: ir.Or):
        # Visit children and get their types (skip first child which is the type)
        _, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"Or must have BoolT type, got {node.T}")
        # Verify operands are Bool
        if not isinstance(aT, ir.BoolT):
            raise TypeError(f"Or operand a must be Bool, got {aT}")
        if not isinstance(bT, ir.BoolT):
            raise TypeError(f"Or operand b must be Bool, got {bT}")
        return node.T

    @handles(ir.Add)
    def _(self, node: ir.Add):
        # Visit children and get their types (skip first child which is the type)
        _, aT, bT = self.visit_children(node)
        # Verify type is IntT
        if not isinstance(node.T, ir.IntT):
            raise TypeError(f"Add must have IntT type, got {node.T}")
        # Verify operands are Int
        if not isinstance(aT, ir.IntT):
            raise TypeError(f"Add operand a must be Int, got {aT}")
        if not isinstance(bT, ir.IntT):
            raise TypeError(f"Add operand b must be Int, got {bT}")
        return node.T

    @handles(ir.Sub)
    def _(self, node: ir.Sub):
        # Visit children and get their types (skip first child which is the type)
        _, aT, bT = self.visit_children(node)
        # Verify type is IntT
        if not isinstance(node.T, ir.IntT):
            raise TypeError(f"Sub must have IntT type, got {node.T}")
        # Verify operands are Int
        if not isinstance(aT, ir.IntT):
            raise TypeError(f"Sub operand a must be Int, got {aT}")
        if not isinstance(bT, ir.IntT):
            raise TypeError(f"Sub operand b must be Int, got {bT}")
        return node.T

    @handles(ir.Mul)
    def _(self, node: ir.Mul):
        # Visit children and get their types (skip first child which is the type)
        _, aT, bT = self.visit_children(node)
        # Verify type is IntT
        if not isinstance(node.T, ir.IntT):
            raise TypeError(f"Mul must have IntT type, got {node.T}")
        # Verify operands are Int
        if not isinstance(aT, ir.IntT):
            raise TypeError(f"Mul operand a must be Int, got {aT}")
        if not isinstance(bT, ir.IntT):
            raise TypeError(f"Mul operand b must be Int, got {bT}")
        return node.T

    @handles(ir.Gt)
    def _(self, node: ir.Gt):
        # Visit children and get their types (skip first child which is the type)
        _, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"Gt must have BoolT type, got {node.T}")
        # Verify operands are Int
        if not isinstance(aT, ir.IntT):
            raise TypeError(f"Gt operand a must be Int, got {aT}")
        if not isinstance(bT, ir.IntT):
            raise TypeError(f"Gt operand b must be Int, got {bT}")
        return node.T

    @handles(ir.GtEq)
    def _(self, node: ir.GtEq):
        # Visit children and get their types (skip first child which is the type)
        _, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"GtEq must have BoolT type, got {node.T}")
        # Verify operands are Int
        if not isinstance(aT, ir.IntT):
            raise TypeError(f"GtEq operand a must be Int, got {aT}")
        if not isinstance(bT, ir.IntT):
            raise TypeError(f"GtEq operand b must be Int, got {bT}")
        return node.T

    @handles(ir.SumReduce)
    def _(self, node: ir.SumReduce):
        # Visit children and get their types (skip first child which is the type)
        _, funcT = self.visit_children(node)
        # Verify type is IntT
        if not isinstance(node.T, ir.IntT):
            raise TypeError(f"SumReduce must have IntT type, got {node.T}")
        # Verify function argument is a Value with FuncT type
        if not isinstance(funcT, ir.FuncT):
            raise TypeError(f"SumReduce expects FuncT argument, got {funcT}")
        if not isinstance(funcT.retT, ir.IntT):
            raise TypeError(f"SumReduce expects FuncT with Int element type, got {funcT.retT}")
        return node.T

    @handles(ir.ProdReduce)
    def _(self, node: ir.ProdReduce):
        # Visit children and get their types (skip first child which is the type)
        _, funcT = self.visit_children(node)
        # Verify type is IntT
        if not isinstance(node.T, ir.IntT):
            raise TypeError(f"ProdReduce must have IntT type, got {node.T}")
        # Verify function argument is a Value with FuncT type
        if not isinstance(funcT, ir.FuncT):
            raise TypeError(f"ProdReduce expects FuncT argument, got {funcT}")
        if not isinstance(funcT.retT, ir.IntT):
            raise TypeError(f"ProdReduce expects FuncT with Int element type, got {funcT.retT}")
        return node.T

    @handles(ir.AllDistinct)
    def _(self, node: ir.AllDistinct):
        # Visit children and get their types (skip first child which is the type)
        _, funcT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"AllDistinct must have BoolT type, got {node.T}")
        # Verify function argument is a Value with FuncT type
        if not isinstance(funcT, ir.FuncT):
            raise TypeError(f"AllDistinct expects FuncT argument, got {funcT}")
        return node.T

    @handles(ir.AllSame)
    def _(self, node: ir.AllSame):
        # Visit children and get their types (skip first child which is the type)
        _, funcT = self.visit_children(node)
        # Verify type is BoolT
        if not isinstance(node.T, ir.BoolT):
            raise TypeError(f"AllSame must have BoolT type, got {node.T}")
        # Verify function argument is a Value with FuncT type
        if not isinstance(funcT, ir.FuncT):
            raise TypeError(f"AllSame expects FuncT argument, got {funcT}")
        return node.T

    ##############################
    ## Constructor-level IR nodes (Used for construction but immediately gets transformed for spec)
    ##############################

    @handles(ir._BoundVarPlaceholder)
    def _(self, node: ir._BoundVarPlaceholder):
        # Visit children (just the type)
        self.visit_children(node)
        return node.T

    @handles(ir._LambdaPlaceholder)
    def _(self, node: ir._LambdaPlaceholder):
        # Visit children and get their types (skip first child which is the type)
        _, boundVarT, bodyT = self.visit_children(node)
        # Verify type is ArrowT
        if not isinstance(node.T, ir.ArrowT):
            raise TypeError(f"_LambdaPlaceholder must have ArrowT type, got {node.T}")
        if not boundVarT.eq(node.T.argT):
            raise TypeError(f"_LambdaPlaceholder bound variable type {boundVarT} does not match ArrowT argument type {node.T.argT}")
        if not bodyT.eq(node.T.resT):
            raise TypeError(f"_LambdaPlaceholder body type {bodyT} does not match ArrowT result type {node.T.resT}")
        return node.T

    @handles(ir._VarPlaceholder)
    def _(self, node: ir._VarPlaceholder):
        # Visit children (just the type)
        self.visit_children(node)
        return node.T
