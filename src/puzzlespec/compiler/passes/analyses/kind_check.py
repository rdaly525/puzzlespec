from __future__ import annotations

from ..pass_base import Context, AnalysisObject, Analysis, handles
from ...dsl import ir
import typing as tp
from ...dsl.utils import _is_type, _is_kind, _is_same_kind, _is_value

class _Map:
    def __init__(self):
        self.Tmap = {}
    def __getitem__(self, key: ir.Node) -> ir.Type:
        return self.Tmap[key]
    def __setitem__(self, key: ir.Node, value: ir.Type):
        if isinstance(value, ir.RefT):
            raise ValueError(f"RefT cannot be set in TypeMap, got {value}")
        self.Tmap[key] = value

class TypeMap(AnalysisObject):
    def __init__(self, Tmap: tp.Dict[ir.Node, ir.Type]):
        self.Tmap = Tmap

# This class Verifies that the IR is well-typed. This includes the Types themselves
class KindCheckingPass(Analysis):
    requires = ()
    produces = (TypeMap,)
    name = "kind_checking"
    
    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.bctx: tp.List[ir.Type] = []
        self.Tmap = _Map()
        self.visit(root)
        return TypeMap(self.Tmap)

    ##############################
    ## Core-level IR Type nodes 
    ##############################

    def visit(self, node: ir.Node):
        raise NotImplementedError(node)

    @handles(ir.UnitT)
    def _(self, node: ir.UnitT):
        # UnitT has no children, nothing to check
        T = node
        self.Tmap[node] = T
        return T

    @handles(ir.BoolT)
    def _(self, node: ir.BoolT):
        # BoolT has no children, nothing to check
        T = node
        self.Tmap[node] = T
        return T

    @handles(ir.IntT)
    def _(self, node: ir.IntT):
        # IntT has no children, nothing to check
        T = node
        self.Tmap[node] = T
        return T

    @handles(ir.EnumT)
    def _(self, node: ir.EnumT):
        # EnumT has no children, nothing to check
        T = node
        self.Tmap[node] = T
        return T

    @handles(ir.TupleT)
    def _(self, node: ir.TupleT):
        # Visit children to verify they are Types
        childTs = self.visit_children(node)
        if not all(_is_type(childT) for childT in childTs):
            raise TypeError(f"TupleT children must be Types, got {childTs}")
        T = node
        self.Tmap[node] = T
        return T

    @handles(ir.SumT)
    def _(self, node: ir.SumT):
        # Visit children to verify they are Types
        childTs = self.visit_children(node)
        if not all(_is_type(childT) for childT in childTs):
            raise TypeError(f"SumT children must be Types, got {childTs}")
        T = node
        self.Tmap[node] = T
        return T

    @handles(ir.DomT)
    def _(self, node: ir.DomT):
        # Visit children to verify they are Types
        factorTs = self.visit_children(node)
        if not all(_is_type(factorT) for factorT in factorTs):
            raise TypeError(f"DomT factors must be Types, got {factorTs}")
        T = node
        self.Tmap[node] = T
        return T

    @handles(ir.PiT)
    def _(self, node: ir.PiT):
        # Verify type is ArrowT
        argT, bodyT = node._children
        # Verify T is a type
        if not _is_type(argT):
            raise TypeError(f"PiT argT must be a type, got {argT}")
        new_argT = self.visit(argT)
        self.bctx.append(new_argT.T)
        # Visit body and get its type
        new_bodyT = self.visit(bodyT)
        if not _is_type(new_bodyT):
            raise TypeError(f"PiT body must be a type, got {new_bodyT}")
        # Pop bound context
        self.bctx.pop()
        T = node
        self.Tmap[node] = T
        return T

    @handles(ir.FuncT)
    def _(self, node: ir.FuncT):
        domT, piT = self.visit_children(node)
        if not _is_kind(domT, ir.DomT):
            raise TypeError(f"FuncT domain must be a domain, got {domT}")
        if not _is_kind(piT, (ir.PiT, ir.PiTHOAS)):
            raise TypeError(f"FuncT lambda must be a lambda, got {piT}")
        # Verify funcT domain carrier type matches piT argument type
        if not _is_same_kind(piT.argT, domT.carT):
            raise TypeError(f"PiT argument type {piT.argT} does not match FuncT domain carrier type {domT.carT}")
        T = node
        self.Tmap[node] = T
        return T

    @handles(ir.RefT)
    def _(self, node: ir.RefT):
        T, domT = self.visit_children(node)
        if not _is_kind(T, ir.Type):
            raise TypeError(f"RefT's underlying type must be a type, got {T}")
        if not _is_kind(domT, ir.DomT):
            raise TypeError(f"RefT's domain must be a domain, got {domT}")
        # dom.T.carT must be T
        if not _is_same_kind(domT.carT, T):
            raise TypeError(f"Refinement Type's T, {T}, does not match domain carrier type {domT.carT}")
        self.Tmap[node] = T
        return T

    
    ##############################
    ## Core-level IR Value nodes (Used throughout entire compiler flow)
    ##############################

    @handles(ir.VarRef)
    def _(self, node: ir.VarRef):
        T, = self.visit_children(node)
        if not _is_type(T):
            raise TypeError(f"Variable with sid={node.sid} has non-type type {T}")
        self.Tmap[node] = T
        return T

    @handles(ir.BoundVar)
    def _(self, node: ir.BoundVar):
        if node.idx >= len(self.bctx):
            raise TypeError(f"BoundVar index {node.idx} out of bounds (bctx length: {len(self.bctx)})")
        T = self.bctx[-(node.idx+1)]
        if not _is_type(T):
            raise TypeError(f"BoundVar index {node.idx} has non-type type {T}")
        if not all(_is_type(t) for t in self.bctx):
            raise TypeError(f"Bound context must contain only types, got {self.bctx}")
        self.Tmap[node] = T
        return T

    @handles(ir.Unit)
    def _(self, node: ir.Unit):
        self.visit_children(node)
        if not _is_kind(node.T, ir.UnitT):
            raise TypeError(f"Unit must have UnitT type, got {node.T}")
        T = node.T
        self.Tmap[node] = T
        return T

    @handles(ir.Lambda)
    def _(self, node: ir.Lambda):
        # Verify type is PiT
        piT, body = node._children
        piT = self.visit(piT)
        if not _is_kind(piT, (ir.PiT, ir.PiTHOAS)):
            raise TypeError(f"Lambda must have PiT type, got {node.T}")
        # Verify body is a Value
        if not _is_value(body):
            raise TypeError(f"Lambda body must be a Value, got {body}")
        # Push parameter type onto bound context for body checking
        self.bctx.append(piT.argT.T)
        # Visit body and get its type
        bodyT = self.visit(body)
        # Pop bound context
        self.bctx.pop()
        # Verify body type matches PiT result type
        if not _is_same_kind(bodyT, piT.resT):
            raise TypeError(f"Lambda body type {bodyT} does not match PiT result type {piT.resT}")
        T = piT
        self.Tmap[node] = T
        return T

    @handles(ir.Lit)
    def _(self, node: ir.Lit):
        # Visit children (just the type)
        T, = self.visit_children(node)
        # Verify type matches the literal value
        # The type should be one of the base types
        if not _is_kind(T, (ir.BoolT, ir.IntT, ir.EnumT)):
            raise TypeError(f"Lit must have BoolT, IntT, or EnumT type, got {T}")
        self.Tmap[node] = T
        return T

    @handles(ir.Eq)
    def _(self, node: ir.Eq):
        T, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Eq must have BoolT type, got {T}")
        # Verify operands have same type
        if not _is_same_kind(aT, bT):
            raise TypeError(f"Eq has operands of inconsistent types: {aT} != {bT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Lt)
    def _(self, node: ir.Lt):
        T, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Lt must have BoolT type, got {node.T}")
        # Verify operands are Int
        if not (_is_kind(aT, ir.IntT) and _is_kind(bT, ir.IntT)):
            raise TypeError(f"Lt expects Int operands, got {aT} and {bT}")
        self.Tmap[node] = T
        return T

    @handles(ir.LtEq)
    def _(self, node: ir.LtEq):
        T, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"LtEq must have BoolT type, got {node.T}")
        # Verify operands are Int
        if not (_is_kind(aT, ir.IntT) and _is_kind(bT, ir.IntT)):
            raise TypeError(f"LtEq expects Int operands, got {aT} and {bT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Ite)
    def _(self, node: ir.Ite):
        T, predT, tT, fT = self.visit_children(node)
        # Verify predicate is Bool
        if not _is_kind(predT, ir.BoolT):
            raise TypeError(f"Ite predicate must be Bool, got {predT}")
        # Verify branches have same type
        if not _is_same_kind(tT, fT):
            raise TypeError(f"Ite branches must have same type: {tT} != {fT}")
        # Verify result type matches branch type
        if not _is_same_kind(node.T, tT):
            raise TypeError(f"Ite result type {node.T} does not match branch type {tT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Not)
    def _(self, node: ir.Not):
        T, aT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Not must have BoolT type, got {T}")
        # Verify operand is Bool
        if not _is_kind(aT, ir.BoolT):
            raise TypeError(f"Not expects Bool operand, got {aT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Neg)
    def _(self, node: ir.Neg):
        T, aT = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"Neg must have IntT type, got {T}")
        # Verify operand is Int
        if not _is_kind(aT, ir.IntT):
            raise TypeError(f"Neg expects Int operand, got {aT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Div)
    def _(self, node: ir.Div):
        T, aT, bT = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"Div must have IntT type, got {node.T}")
        # Verify operands are Int
        if not (_is_kind(aT, ir.IntT) and _is_kind(bT, ir.IntT)):
            raise TypeError(f"Div expects Int operands, got {aT} and {bT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Mod)
    def _(self, node: ir.Mod):
        T, aT, bT = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"Mod must have IntT type, got {node.T}")
        # Verify operands are Int
        if not (_is_kind(aT, ir.IntT) and _is_kind(bT, ir.IntT)):
            raise TypeError(f"Mod expects Int operands, got {aT} and {bT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Conj)
    def _(self, node: ir.Conj):
        T, *childTs = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Conj must have BoolT type, got {node.T}")
        # Verify all operands are Bool
        for i, childT in enumerate(childTs):
            if not _is_kind(childT, ir.BoolT):
                raise TypeError(f"Conj child {i} must be Bool, got {childT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Disj)
    def _(self, node: ir.Disj):
        T, childTs = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Disj must have BoolT type, got {node.T}")
        # Verify all operands are Bool
        for i, childT in enumerate(childTs):
            if not _is_kind(childT, ir.BoolT):
                raise TypeError(f"Disj child {i} must be Bool, got {childT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Sum)
    def _(self, node: ir.Sum):
        T, *childTs = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"Sum must have IntT type, got {node.T}")
        # Verify all operands are Int
        for i, childT in enumerate(childTs):
            if not _is_kind(childT, ir.IntT):
                raise TypeError(f"Sum child {i} must be Int, got {childT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Prod)
    def _(self, node: ir.Prod):
        T, *childTs = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"Prod must have IntT type, got {node.T}")
        # Verify all operands are Int
        for i, childT in enumerate(childTs):
            if not _is_kind(childT, ir.IntT):
                raise TypeError(f"Prod child {i} must be Int, got {childT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Universe)
    def _(self, node: ir.Universe):
        # Visit children (just the type)
        T, = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"Universe must have DomT type, got {node.T}")
        self.Tmap[node] = T
        return T

    @handles(ir.Fin)
    def _(self, node: ir.Fin):
        T, NT = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"Fin must have DomT type, got {node.T}")
        # Verify N argument is Int
        if not _is_kind(NT, ir.IntT):
            raise TypeError(f"Fin expects Int argument, got {NT}")
        if not _is_kind(T.carT, ir.IntT):
            raise TypeError(f"Fin domain carrier type must be Int, got {T.carT}")
        if T.rank != 1 or T.axes[0] != 0:
            raise TypeError(f"Fin domain must be rank 1, got {T.axes}")        
        if not T.fin:
            raise TypeError(f"Fin domain must be finite, got {T.fins}")
        if not T.ord:
            raise TypeError(f"Fin domain must be ordered, got {T.ords}")
        self.Tmap[node] = T
        return T

    @handles(ir.Range)
    def _(self, node: ir.Range):
        T, loT, hiT = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"Range must have DomT type, got {node.T}")
        # Verify N argument is Int
        if not _is_kind(loT, ir.IntT) or not _is_kind(hiT, ir.IntT):
            raise TypeError(f"Range expects Int arguments, got {loT} and {hiT}")
        if not _is_kind(T.carT, ir.IntT):
            raise TypeError(f"Range domain carrier type must be Int, got {T.carT}")
        if T.rank != 1 or T.axes[0] != 0:
            raise TypeError(f"Fin domain must be rank 1, got {T.axes}")        
        if not T.fin:
            raise TypeError(f"Fin domain must be finite, got {T.fins}")
        if not T.ord:
            raise TypeError(f"Fin domain must be ordered, got {T.ords}")
        self.Tmap[node] = T
        return T

    @handles(ir.EnumLit)
    def _(self, node: ir.EnumLit):
        # Visit children (just the type)
        T, = self.visit_children(node)
        # Verify type is EnumT
        if not _is_kind(T, ir.EnumT):
            raise TypeError(f"EnumLit must have EnumT type, got {node.T}")
        # Verify label is in the enum
        if not _is_kind(T, ir.EnumT):
            raise TypeError(f"EnumLit must have EnumT type, got {node.T}")
        if node.label not in T.labels:
            raise TypeError(f"EnumLit label '{node.label}' not in enum labels {T.labels}")
        self.Tmap[node] = T
        return T

    @handles(ir.DomLit)
    def _(self, node: ir.DomLit):
        T, *elemTs = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"DomLit must have DomT type, got {T}")
        # Verify all elements have the same type
        if len(elemTs) > 0:
            first_elemT = elemTs[0]
            for i, elemT in enumerate(elemTs):
                if not _is_same_kind(elemT, first_elemT):
                    raise TypeError(f"DomLit element {i} has type {elemT} which differs from first element type {first_elemT}")
            # Verify element type matches domain carrier type
            if not _is_same_kind(first_elemT, T.carT):
                raise TypeError(f"DomLit element type {first_elemT} does not match domain carrier type {T.carT}")
        self.Tmap[node] = T
        return T

    @handles(ir.SumLit)
    def _(self, node: ir.SumLit):
        T, tagT, *elemTs = self.visit_children(node)
        # Verify type is SumT
        if not _is_kind(T, ir.SumT):
            raise TypeError(f"SumLit must have SumT type, got {T}")
        # Verify tag is IntT
        if not _is_kind(tagT, ir.IntT):
            raise TypeError(f"SumLit tag must be IntT, got {tagT}")
        # Verify number of elements matches SumT
        if len(elemTs) != len(T.elemTs):
            raise TypeError(f"SumLit has {len(elemTs)} elements but SumT has {len(T.elemTs)} variants")
        # Verify each element type matches corresponding SumT element type
        for i, (elemT, sumElemT) in enumerate(zip(elemTs, T.elemTs)):
            if not _is_same_kind(elemT, sumElemT):
                raise TypeError(f"SumLit element {i} type {elemT} does not match SumT element type {sumElemT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Card)
    def _(self, node: ir.Card):
        T, domainT = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"Card must have IntT type, got {T}")
        # Verify domain argument is a domain
        if not _is_kind(domainT, ir.DomT):
            raise TypeError(f"Card expects domain argument, got {domainT}")
        if not domainT.fin:
            raise TypeError(f"Card expects finite domain, got {domainT}")
        self.Tmap[node] = T
        return T

    @handles(ir.ElemAt)
    def _(self, node: ir.ElemAt):
        T, domainT, idxT = self.visit_children(node)
        # Verify domain argument is a domain
        if not _is_kind(domainT, ir.DomT):
            raise TypeError(f"ElemAt expects domain argument, got {domainT}")
        if not _is_kind(idxT, ir.IntT):
            raise TypeError(f"ElemAt expects Int index, got {idxT}")
        if not _is_same_kind(T, domainT.carT):
            raise TypeError(f"ElemAt result type {T} does not match domain carrier type {domainT.carT}")
        self.Tmap[node] = T
        return T

    @handles(ir.IsMember)
    def _(self, node: ir.IsMember):
        T, domainT, valT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"IsMember must have BoolT type, got {node.T}")
        # Verify domain argument is a domain
        if not _is_kind(domainT, ir.DomT):
            raise TypeError(f"IsMember expects domain argument, got {domainT}")
        # Verify value argument type matches domain carrier type
        if not _is_same_kind(valT, domainT.carT):
            raise TypeError(f"IsMember value type {valT} does not match domain carrier type {domainT.carT}")
        self.Tmap[node] = T
        return T

    @handles(ir.CartProd)
    def _(self, node: ir.CartProd):
        T, *domTs = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"CartProd must have DomT type, got {node.T}")
        # Verify all arguments are domains
        for i, domT in enumerate(domTs):
            if not _is_kind(domT, ir.DomT):
                raise TypeError(f"CartProd argument {i} must be a domain, got {domT}")
        for i, (domT, factorT) in enumerate(zip(domTs, T.factors)):
            if not _is_same_kind(domT.carT, factorT):
                raise TypeError(f"CartProd argument {i} type {domT} does not match domain factor type {factorT}")
        self.Tmap[node] = T
        return T

    @handles(ir.DomProj)
    def _(self, node: ir.DomProj):
        T, domT = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"DomProj must have DomT type, got {T}")
        # Verify domain argument is a domain
        if not _is_kind(domT, ir.DomT):
            raise TypeError(f"DomProj expects domain argument, got {domT}")
        if node.idx >= len(domT.factors):
            raise TypeError(f"DomProj index {node.idx} out of bounds for tuple of length {len(domT.factors)}")
        if not _is_same_kind(T.carT, domT.factors[node.idx]):
            raise TypeError(f"DomProj result type {node.T} does not match domain factor type {domT.factors[node.idx]}")
        if T.fin != domT.fins[node.idx]:
            raise TypeError(f"DomProj result domain must be finite, got {T.fin}")
        if T.ord != domT.ords[node.idx]:
            raise TypeError(f"DomProj result domain must be ordered, got {T.ord}")
        self.Tmap[node] = T
        return T

    @handles(ir.TupleLit)
    def _(self, node: ir.TupleLit):
        T, *valTs = self.visit_children(node)
        # Verify type is TupleT
        if not _is_kind(T, ir.TupleT):
            raise TypeError(f"TupleLit must have TupleT type, got {T}")
        # Verify all value arguments match tuple element types
        if len(valTs) != len(T.elemTs):
            raise TypeError(f"TupleLit has {len(valTs)} values ({valTs}) but type has {len(T.elemTs)} elements ({T.elemTs})")
        for i, (valT, elemT) in enumerate(zip(valTs, T.elemTs)):
            if not _is_same_kind(valT, elemT):
                raise TypeError(f"TupleLit value {i} type {valT} does not match tuple element type {elemT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Proj)
    def _(self, node: ir.Proj):
        T, tupT = self.visit_children(node)
        # Verify tuple argument is a Value with TupleT type
        if not _is_kind(tupT, ir.TupleT):
            raise TypeError(f"Proj expects tuple argument, got {tupT}")
        if node.idx >= len(tupT.elemTs):
            raise TypeError(f"Proj index {node.idx} out of bounds for tuple of length {len(tupT.elemTs)}")
        # Verify result type matches projected element type
        if not _is_same_kind(T, tupT.elemTs[node.idx]):
            raise TypeError(f"Proj result type {node.T} does not match tuple element type {tupT.elemTs[node.idx]}")
        self.Tmap[node] = T
        return T

    @handles(ir.DisjUnion)
    def _(self, node: ir.DisjUnion):
        T, *domTs = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"DisjUnion must have DomT type, got {node.T}")
        # Verify all arguments are domains
        for i, domT in enumerate(domTs):
            if not _is_kind(domT, ir.DomT):
                raise TypeError(f"DisjUnion argument {i} must be a domain, got {domT}")
        if not _is_kind(T.carT, ir.SumT):
            raise TypeError(f"DisjUnion must have sum carrier type, got {T.carT}")
        self.Tmap[node] = T
        return T

    @handles(ir.DomInj)
    def _(self, node: ir.DomInj):
        T, domT = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"DomInj must have DomT type, got {T}")
        # Verify domain argument is a domain
        if not _is_kind(domT, ir.DomT):
            raise TypeError(f"DomInj expects domain argument, got {domT}")
        if not _is_kind(domT.carT, ir.SumT):
            raise TypeError(f"DomInj must have sum carrier type, got {domT.carT}")
        if node.idx >= len(domT.carT.elemTs):
            raise TypeError(f"DomInj index {node.idx} out of bounds for sum of length {len(domT.carT.elemTs)}")
        if not _is_same_kind(T.carT.elemTs[node.idx], domT.carT):
            raise TypeError(f"DomInj's result carT {T.carT.elemTs[node.idx]} does not match domain carT {domT.carT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Inj)
    def _(self, node: ir.Inj):
        T, valT = self.visit_children(node)
        if not _is_kind(T, ir.SumT):
            raise TypeError(f"Inj must have SumT type, got {T}")
        if node.idx >= len(T.elemTs):
            raise TypeError(f"Inj index {node.idx} out of bounds for sum of length {len(T.elemTs)}")
        if not _is_same_kind(valT, T.elemTs[node.idx]):
            raise TypeError(f"Inj's value type {valT} does not match sum element type {T.elemTs[node.idx]} of sum {T}")
        self.Tmap[node] = T
        return T

    @handles(ir.Match)
    def _(self, node: ir.Match):
        T, scrutT, *branchesT = self.visit_children(node)
        # Verify scrutinee is a Value with SumT type
        if not _is_kind(scrutT, ir.SumT):
            raise TypeError(f"Match scrutinee must be SumT, got {scrutT}")
        # Verify branches is a Value with TupleT type
        if len(branchesT) != len(scrutT.elemTs):
            raise TypeError(f"Match branches count {len(branchesT)} does not match sum type count {len(scrutT.elemTs)}")
        for i, (sum_elem_T, branch_T) in enumerate(zip(scrutT.elemTs, branchesT)):
            if not _is_kind(branch_T, (ir.PiT, ir.PiTHOAS)):
                raise TypeError(f"Match branch {i} must be lambdaT matching sum component {sum_elem_T} to match result type {T}. Got {branch_T}")
            # Verify branch argument type matches sum component
            if not _is_same_kind(branch_T.argT, sum_elem_T):
                raise TypeError(f"Match branch {i} argument type {branch_T.argT} does not match sum component {sum_elem_T}")
            if not _is_same_kind(branch_T.resT, T):
                raise TypeError(f"Match branch {i} result type {branch_T.resT} does not match match result type {T}")
        self.Tmap[node] = T
        return T

    @handles(ir.Restrict)
    def _(self, node: ir.Restrict):
        T, funcT = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"Restrict must have DomT type, got {T}")
        # Verify function argument is a FuncT
        if not _is_kind(funcT, ir.FuncT):
            raise TypeError(f"Restrict expects FuncT argument, got {funcT}")
        # Verify function returns Bool
        if not _is_kind(funcT.piT.resT, ir.BoolT):
            raise TypeError(f"Restrict expects FuncT with Bool result type, got {funcT.piT.resT}")
        # Verify function argument type matches domain carrier type
        domainT = funcT.dom.T
        if not _is_same_kind(funcT.piT.argT, domainT.carT):
            raise TypeError(f"Restrict function argument type {funcT.piT.argT} does not match domain carrier type {domainT.carT}")
        # Verify result carrier type matches domain carrier type
        if not _is_same_kind(T.carT, domainT.carT):
            raise TypeError(f"Restrict result carrier type {T.carT} does not match domain carrier type {domainT.carT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Forall)
    def _(self, node: ir.Forall):
        T, funcT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Forall must have BoolT type, got {T}")
        # Verify function argument is a FuncT
        if not _is_kind(funcT, ir.FuncT):
            raise TypeError(f"Forall expects FuncT argument, got {funcT}")
        # Verify function returns Bool
        if not _is_kind(funcT.piT.resT, ir.BoolT):
            raise TypeError(f"Forall expects FuncT with Bool result type, got {funcT.piT.resT}")
        # Verify function argument type matches domain carrier type
        self.Tmap[node] = T
        return T

    @handles(ir.Exists)
    def _(self, node: ir.Exists):
        T, funcT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Exists must have BoolT type, got {T}")
        # Verify function argument is a FuncT
        if not _is_kind(funcT, ir.FuncT):
            raise TypeError(f"Exists expects FuncT argument, got {funcT}")
        # Verify function returns Bool
        if not _is_kind(funcT.piT.resT, ir.BoolT):
            raise TypeError(f"Exists expects FuncT with Bool result type, got {funcT.piT.resT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Map)
    def _(self, node: ir.Map):
        T, domT, funT = self.visit_children(node)
        # Verify type is funcT
        if not _is_kind(T, ir.FuncT):
            raise TypeError(f"Map must have FuncT type, got {T}")
        # Verify domain argument is a domain
        if not _is_kind(domT, ir.DomT):
            raise TypeError(f"Map expects domain argument, got {domT}")
        # Verify function is a PiT
        if not _is_kind(funT, (ir.PiT, ir.PiTHOAS)):
            raise TypeError(f"Map expects PiT function, got {funT}")
        if not _is_same_kind(funT.argT, domT.carT):
            raise TypeError(f"Map function argument type {funT.argT} does not match domain carrier type {domT.carT}")
        if not _is_same_kind(T.piT.resT, funT.resT):
            raise TypeError(f"Map result type {T.lam.resT} does not match function result type {funT.resT}")
        self.Tmap[node] = T
        return T

    @handles(ir.FuncLit)
    def _(self, node: ir.FuncLit):
        T, domT, *elemsT = self.visit_children(node)
        # Verify type is FuncT
        if not _is_kind(T, ir.FuncT):
            raise TypeError(f"FuncLit must have FuncT type, got {T}")
        # Verify domain argument is a domain
        if not _is_kind(domT, ir.DomT):
            raise TypeError(f"FuncLit expects domain argument, got {domT}")
        if isinstance(node.layout, ir._DenseLayout):
            if len(elemsT) != len(node.layout.val_map):
                raise TypeError(f"FuncLit has {len(elemsT)} elements but layout has {len(node.layout.val_map)} elements")
            for i, elemT in enumerate(elemsT):
                if not _is_same_kind(elemT, T.piT.resT):
                    raise TypeError(f"FuncLit element {i} type {elemT} does not match function result type {T.piT.resT}")
        elif isinstance(node.layout, ir._SparseLayout):
            raise NotImplementedError("SparseFuncLit not implemented")
        else:
            raise NotImplementedError(f"Unsupported FuncLit layout: {node.layout}")
        self.Tmap[node] = T
        return T

    @handles(ir.Image)
    def _(self, node: ir.Image):
        raise NotImplementedError("Image not implemented")
        _, funcT = self.visit_children(node)
        # Verify type is DomT
        if not isinstance(node.T, ir.DomT):
            raise TypeError(f"Image must have DomT type, got {node.T}")
        # Verify function argument is a Value with FuncT type
        if not isinstance(funcT, ir.FuncT):
            raise TypeError(f"Image expects FuncT argument, got {funcT}")
        if not node.T.eq(funcT.resT):
            raise TypeError(f"Image result type {node.T} does not match function result type {funcT.resT}")
        T = node.T
        self.Tmap[node] = T
        return T

    @handles(ir.ApplyFunc)
    def _(self, node: ir.ApplyFunc):
        T, funcT, argT = self.visit_children(node)
        # Verify function argument is a FuncT
        if not _is_kind(funcT, ir.FuncT):
            raise TypeError(f"ApplyFunc expects FuncT function, got {funcT}")
        # Verify argument type matches function domain carrier type
        if not _is_same_kind(argT, funcT.dom.T.carT):
            raise TypeError(f"ApplyFunc argument type {argT} does not match function domain carrier type {funcT.dom.T.carT}")
        # Verify result type matches function result type
        if not _is_same_kind(T, funcT.piT.resT):
            raise TypeError(f"ApplyFunc result type {T} does not match function result type {funcT.piT.resT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Apply)
    def _(self, node: ir.Apply):
        T, lamT, argT = self.visit_children(node)
        # Verify lambda has PiT type
        if not _is_kind(lamT, (ir.PiT, ir.PiTHOAS)):
            raise TypeError(f"Apply expects Lambda with PiT type, got {lamT}")
        # Verify argument type matches lambda argument type
        if not _is_same_kind(argT, lamT.argT):
            raise TypeError(f"Apply argument type {argT} does not match lambda argument type {lamT.argT}")
        # Verify result type matches lambda result type
        if not _is_same_kind(T, lamT.resT):
            raise TypeError(f"Apply result type {T} does not match lambda result type {lamT.resT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Fold)
    def _(self, node: ir.Fold):
        T, funcT, funT, initT = self.visit_children(node)
        # Verify function argument is a FuncT
        if not _is_kind(funcT, ir.FuncT):
            raise TypeError(f"Fold expects FuncT function, got {funcT}")
        # Verify fun argument is a Lambda with PiT type
        if not _is_kind(funT, (ir.PiT, ir.PiTHOAS)):
            raise TypeError(f"Fold expects Lambda with PiT type, got {funT}")
        # Fold signature: Func(Dom(A)->B) -> ((A,B) -> B) -> B -> B
        # So fun should be (elemT, resT) -> resT where elemT = funcT.piT.resT
        elemT = funcT.piT.resT
        resT = funT.resT
        # Verify fun argument type is TupleT(elemT, resT)
        if not _is_kind(funT.argT, ir.TupleT):
            raise TypeError(f"Fold fun argument type must be TupleT, got {funT.argT}")
        if len(funT.argT) != 2:
            raise TypeError(f"Fold fun argument tuple must have 2 elements, got {len(funT.argT)}")
        if not _is_same_kind(funT.argT[0], elemT):
            raise TypeError(f"Fold fun argument tuple first element type {funT.argT[0]} does not match function element type {elemT}")
        if not _is_same_kind(funT.argT[1], resT):
            raise TypeError(f"Fold fun argument tuple second element type {funT.argT[1]} does not match result type {resT}")
        # Verify init type matches result type
        if not _is_same_kind(initT, resT):
            raise TypeError(f"Fold init type {initT} does not match function result type {resT}")
        # Verify result type matches
        if not _is_same_kind(T, resT):
            raise TypeError(f"Fold result type {T} does not match expected type {resT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Slice)
    def _(self, node: ir.Slice):
        T, domT, loT, hiT = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"Slice must have DomT type, got {T}")
        # Verify domain argument is a domain
        if not _is_kind(domT, ir.DomT):
            raise TypeError(f"Slice expects domain argument, got {domT}")
        # Verify lo and hi are Int
        if not _is_kind(loT, ir.IntT):
            raise TypeError(f"Slice lo must be Int, got {loT}")
        if not _is_kind(hiT, ir.IntT):
            raise TypeError(f"Slice hi must be Int, got {hiT}")
        if not _is_same_kind(domT.carT, T.carT):
            raise TypeError(f"Slice result type {T.carT} does not match domain carrier type {domT.carT}")
        self.Tmap[node] = T
        return T

    @handles(ir.RestrictEq)
    def _(self, node: ir.RestrictEq):
        T, domT, idxT = self.visit_children(node)
        # Verify domain argument is a domain
        if not _is_kind(domT, ir.DomT):
            raise TypeError(f"Index expects domain argument, got {domT}")
        if not _is_same_kind(idxT, domT.carT):
            raise TypeError(f"Index idx type {idxT} does not match domain carrier type {domT.carT}")
        # Index only works on rank 1 domains
        if domT.rank != 1:
            raise TypeError(f"Index only works on rank 1 domains, got {domT.rank}")
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"Index result type {T} must be a domain, got {T}")
        if not _is_same_kind(T.carT, domT.factors[domT.axes[0]]):
            raise TypeError(f"Index result domain factor type {T.carT} does not match domain factor type {domT.factors[domT.axes[0]]}")
        if T.fin != domT.fins[domT.axes[0]]:
            raise TypeError(f"Index result domain must be finite, got {T.fin} != {domT.fins[domT.axes[0]]}")
        if T.ord != domT.ords[domT.axes[0]]:
            raise TypeError(f"Index result domain must be ordered, got {T.ord} != {domT.ords[domT.axes[0]]}")
        self.Tmap[node] = T
        return T

    ##############################
    ## Surface-level IR nodes (Used for analysis, but can be collapsed)
    ##############################

    # Should always be root
    @handles(ir.Spec)
    def _(self, node: ir.Spec):
        consT, oblsT = self.visit_children(node)
        # Verify cons is a TupleLit
        for T in (consT, oblsT):
            if not _is_kind(T, ir.TupleT):
                raise TypeError(f"Spec cons/obls must be a TupleT, got {type(T)}")
            if not all(_is_kind(c, ir.BoolT) for c in T._children):
                raise TypeError(f"Spec cons/obls must have BoolT children, got {T}")
        T = ir.BoolT()
        self.Tmap[node] = T
        return T

    @handles(ir.And)
    def _(self, node: ir.And):
        T, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"And must have BoolT type, got {T}")
        # Verify operands are Bool
        if not _is_kind(aT, ir.BoolT):
            raise TypeError(f"And operand a must be Bool, got {aT}")
        if not _is_kind(bT, ir.BoolT):
            raise TypeError(f"And operand b must be Bool, got {bT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Implies)
    def _(self, node: ir.Implies):
        T, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Implies must have BoolT type, got {T}")
        # Verify operands are Bool
        if not _is_kind(aT, ir.BoolT):
            raise TypeError(f"Implies operand a must be Bool, got {aT}")
        if not _is_kind(bT, ir.BoolT):
            raise TypeError(f"Implies operand b must be Bool, got {bT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Or)
    def _(self, node: ir.Or):
        T, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Or must have BoolT type, got {T}")
        # Verify operands are Bool
        if not _is_kind(aT, ir.BoolT):
            raise TypeError(f"Or operand a must be Bool, got {aT}")
        if not _is_kind(bT, ir.BoolT):
            raise TypeError(f"Or operand b must be Bool, got {bT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Add)
    def _(self, node: ir.Add):
        T, aT, bT = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"Add must have IntT type, got {T}")
        # Verify operands are Int
        if not _is_kind(aT, ir.IntT):
            raise TypeError(f"Add operand a must be Int, got {aT}")
        if not _is_kind(bT, ir.IntT):
            raise TypeError(f"Add operand b must be Int, got {bT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Sub)
    def _(self, node: ir.Sub):
        T, aT, bT = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"Sub must have IntT type, got {T}")
        # Verify operands are Int
        if not _is_kind(aT, ir.IntT):
            raise TypeError(f"Sub operand a must be Int, got {aT}")
        if not _is_kind(bT, ir.IntT):
            raise TypeError(f"Sub operand b must be Int, got {bT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Mul)
    def _(self, node: ir.Mul):
        T, aT, bT = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"Mul must have IntT type, got {T}")
        # Verify operands are Int
        if not _is_kind(aT, ir.IntT):
            raise TypeError(f"Mul operand a must be Int, got {aT}")
        if not _is_kind(bT, ir.IntT):
            raise TypeError(f"Mul operand b must be Int, got {bT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Abs)
    def _(self, node: ir.Abs):
        T, aT = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"Abs must have IntT type, got {T}")
        # Verify operand is Int
        if not _is_kind(aT, ir.IntT):
            raise TypeError(f"Abs operand must be Int, got {aT}")
        self.Tmap[node] = T
        return T

    @handles(ir.Gt)
    def _(self, node: ir.Gt):
        T, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Gt must have BoolT type, got {T}")
        # Verify operands are Int
        if not _is_kind(aT, ir.IntT):
            raise TypeError(f"Gt operand a must be Int, got {aT}")
        if not _is_kind(bT, ir.IntT):
            raise TypeError(f"Gt operand b must be Int, got {bT}")
        self.Tmap[node] = T
        return T

    @handles(ir.GtEq)
    def _(self, node: ir.GtEq):
        T, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"GtEq must have BoolT type, got {T}")
        # Verify operands are Int
        if not _is_kind(aT, ir.IntT):
            raise TypeError(f"GtEq operand a must be Int, got {aT}")
        if not _is_kind(bT, ir.IntT):
            raise TypeError(f"GtEq operand b must be Int, got {bT}")
        self.Tmap[node] = T
        return T

    @handles(ir.SumReduce)
    def _(self, node: ir.SumReduce):
        T, funcT = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"SumReduce must have IntT type, got {T}")
        # Verify function argument is a FuncT
        if not _is_kind(funcT, ir.FuncT):
            raise TypeError(f"SumReduce expects FuncT argument, got {funcT}")
        if not _is_kind(funcT.piT.resT, ir.IntT):
            raise TypeError(f"SumReduce expects FuncT with Int result type, got {funcT.piT.resT}")
        self.Tmap[node] = T
        return T

    @handles(ir.ProdReduce)
    def _(self, node: ir.ProdReduce):
        T, funcT = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"ProdReduce must have IntT type, got {T}")
        # Verify function argument is a Value with FuncT   type
        if not _is_kind(funcT, ir.FuncT):
            raise TypeError(f"ProdReduce expects FuncT argument, got {funcT}")
        if not _is_same_kind(funcT.piT.resT, ir.IntT):
            raise TypeError(f"ProdReduce expects FuncT with Int result type, got {funcT.piT.resT}")
        self.Tmap[node] = T
        return T

    @handles(ir.AllDistinct)
    def _(self, node: ir.AllDistinct):
        T, funcT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"AllDistinct must have BoolT type, got {T}")
        # Verify function argument is a Value with FuncT type
        if not _is_kind(funcT, ir.FuncT):
            raise TypeError(f"AllDistinct expects FuncT argument, got {funcT}")
        self.Tmap[node] = T
        return T

    @handles(ir.AllSame)
    def _(self, node: ir.AllSame):
        T, funcT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"AllSame must have BoolT type, got {T}")
        # Verify function argument is a Value with FuncT type
        if not _is_kind(funcT, ir.FuncT):
            raise TypeError(f"AllSame expects FuncT argument, got {funcT}")
        self.Tmap[node] = T
        return T

    ##############################
    ## Constructor-level IR nodes (Used for construction but immediately gets transformed for spec)
    ##############################

    @handles(ir.BoundVarHOAS)
    def _(self, node: ir.BoundVarHOAS):
        T, = self.visit_children(node)
        self.Tmap[node] = T
        return T

    @handles(ir.LambdaHOAS)
    def _(self, node: ir.LambdaHOAS):
        T, boundVarT, bodyT = self.visit_children(node)
        # Verify type is PiT
        if not _is_kind(T, (ir.PiT, ir.PiTHOAS)):
            raise TypeError(f"LambdaHOAS must have PiT type, got {T}")
        if not _is_same_kind(boundVarT, T.argT):
            raise TypeError(f"LambdaHOAS bound variable type {boundVarT} does not match PiT argument type {T.argT}")
        if not _is_same_kind(bodyT, T.resT):
            raise TypeError(f"LambdaHOAS body type {bodyT} does not match PiT result type {T.resT}")
        self.Tmap[node] = T
        return T
    
    @handles(ir.PiTHOAS)
    def _(self, node: ir.PiTHOAS):
        bv_T, resT = self.visit_children(node)
        if not _is_type(resT):
            raise TypeError(f"PiTHOAS return type {resT} must be a type")
        if not _is_type(bv_T):
            raise TypeError(f"PiTHOAS bound variable type {bv_T} must be a type")
        T = node
        self.Tmap[node] = T
        return T

    @handles(ir.VarHOAS)
    def _(self, node: ir.VarHOAS):
        T, = self.visit_children(node)
        self.Tmap[node] = T
        return T
