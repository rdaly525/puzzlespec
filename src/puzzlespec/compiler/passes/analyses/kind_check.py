from __future__ import annotations

from ..pass_base import Context, AnalysisObject, Analysis, handles
from ..envobj import EnvsObj, TypeEnv
from ...dsl import ir
import typing as tp
from ...dsl.utils import _is_type, _get_T, _is_kind, _is_same_kind, _is_value

class KindCheckResult(AnalysisObject):
    def __init__(self, Tmap: tp.Dict[ir.Node, ir.Type]):
        self.Tmap = Tmap

# This class Verifies that the IR is well-typed. This includes the Types themselves
class KindCheckingPass(Analysis):
    requires = (EnvsObj,)
    produces = ()
    name = "kind_checking"
    
    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.tenv: TypeEnv = ctx.get(EnvsObj).tenv
        self.bctx: tp.List[ir.Type] = []
        self.visit(root)
        return KindCheckResult(self._cache)

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
        if not all(_is_type(childT) for childT in childTs):
            raise TypeError(f"TupleT children must be Types, got {childTs}")
        return node

    @handles(ir.SumT)
    def _(self, node: ir.SumT):
        # Visit children to verify they are Types
        childTs = self.visit_children(node)
        if not all(_is_type(childT) for childT in childTs):
            raise TypeError(f"SumT children must be Types, got {childTs}")
        return node

    @handles(ir.DomT)
    def _(self, node: ir.DomT):
        # Visit children to verify they are Types
        factorTs = self.visit_children(node)
        if not all(_is_type(factorT) for factorT in factorTs):
            raise TypeError(f"DomT factors must be Types, got {factorTs}")
        return node

    @handles(ir.LambdaT)
    def _(self, node: ir.LambdaT):
        # Verify type is ArrowT
        argT, bodyT = node._children
        # Verify T is a type
        if not _is_type(argT):
            raise TypeError(f"LambdaT argT must be a type, got {argT}")
        new_argT = self.visit(argT)
        self.bctx.append(new_argT)
        # Visit body and get its type
        new_bodyT = self.visit(bodyT)
        if not _is_type(new_bodyT):
            raise TypeError(f"LambdaT body must be a type, got {new_bodyT}")
        # Pop bound context
        self.bctx.pop()
        return node

    @handles(ir.PiT)
    def _(self, node: ir.PiT):
        domT, lamT = self.visit_children(node)
        if not _is_kind(domT, ir.DomT):
            raise TypeError(f"PiT domain must be a domain, got {domT}")
        if not _is_kind(lamT, (ir.LambdaT, ir._LambdaTPlaceholder)):
            raise TypeError(f"PiT lambda must be a lambda, got {lamT}")
        # Verify piT domain carrier type matches lambdaT argument type
        if not _is_same_kind(lamT.argT, _get_T(domT).carT):
            raise TypeError(f"LambdaT argument type {lamT.argT} does not match PiT domain carrier type {domT.carT}")
        return node

    @handles(ir.ApplyT)
    def _(self, node: ir.ApplyT):
        piT, argT = self.visit_children(node)
        if not _is_kind(piT, ir.PiT):
            raise TypeError(f"ApplyT piT must be a pi, got {piT}")
        if not _is_type(argT):
            raise TypeError(f"ApplyT argT must be a type, got {argT}")
        # Verify argument type matches piT domain carrier type
        piT = _get_T(piT)
        if not _is_same_kind(argT, _get_T(piT.dom.T).carT):
            raise TypeError(f"ApplyT argument type {argT} does not match PiT domain carrier type {_get_T(piT.dom.T).carT}")
        return node
    
    ##############################
    ## Core-level IR Value nodes (Used throughout entire compiler flow)
    ##############################

    @handles(ir.VarRef)
    def _(self, node: ir.VarRef):
        if node.sid not in self.tenv:
            raise TypeError(f"Variable with sid={node.sid} not found in type environment")
        T = self.tenv[node.sid]
        if not _is_type(T):
            raise TypeError(f"Variable with sid={node.sid} has non-type type {T}")
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
        return self.bctx[-(node.idx+1)]

    @handles(ir.Unit)
    def _(self, node: ir.Unit):
        self.visit_children(node)
        if not _is_kind(node.T, ir.UnitT):
            raise TypeError(f"Unit must have UnitT type, got {node.T}")
        return node.T

    @handles(ir.Lambda)
    def _(self, node: ir.Lambda):
        # Verify type is LambdaT
        lamT, body = node._children
        lamT = self.visit(lamT)
        if not _is_kind(lamT, (ir.LambdaT, ir._LambdaTPlaceholder)):
            raise TypeError(f"Lambda must have LambdaT type, got {node.T}")
        # Verify body is a Value
        if not _is_value(body):
            raise TypeError(f"Lambda body must be a Value, got {body}")
        # Push parameter type onto bound context for body checking
        self.bctx.append(lamT.argT)
        # Visit body and get its type
        bodyT = self.visit(body)
        # Pop bound context
        self.bctx.pop()
        # Verify body type matches LambdaT result type
        if not _is_same_kind(bodyT, lamT.retT):
            raise TypeError(f"Lambda body type {bodyT} does not match LambdaT result type {lamT.retT}")
        return lamT

    @handles(ir.Lit)
    def _(self, node: ir.Lit):
        # Visit children (just the type)
        T, = self.visit_children(node)
        # Verify type matches the literal value
        # The type should be one of the base types
        if not _is_kind(T, (ir.BoolT, ir.IntT, ir.EnumT)):
            raise TypeError(f"Lit must have BoolT, IntT, or EnumT type, got {T}")
        return T

    @handles(ir.Eq)
    def _(self, node: ir.Eq):
        T, aT, bT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Eq must have BoolT type, got {T}")
        # Verify operands have same type
        if not _is_same_kind(aT, bT):
            print(_get_T(aT), _get_T(bT))
            raise TypeError(f"Eq has operands of inconsistent types: {aT} != {bT}")
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
        return T

    @handles(ir.Conj)
    def _(self, node: ir.Conj):
        T, childTs = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Conj must have BoolT type, got {node.T}")
        # Verify all operands are Bool
        for i, childT in enumerate(childTs):
            if not _is_kind(childT, ir.BoolT):
                raise TypeError(f"Conj child {i} must be Bool, got {childT}")
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
        return T

    @handles(ir.Universe)
    def _(self, node: ir.Universe):
        # Visit children (just the type)
        T, = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"Universe must have DomT type, got {node.T}")
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
        domT = _get_T(T)
        if not _is_kind(domT.carT, ir.IntT):
            raise TypeError(f"Fin domain carrier type must be Int, got {domT.carT}")
        if domT.rank != 1 or domT.axes[0] != 0:
            raise TypeError(f"Fin domain must be rank 1, got {domT.axes}")        
        if not domT.fin:
            raise TypeError(f"Fin domain must be finite, got {domT.fins}")
        if not domT.ord:
            raise TypeError(f"Fin domain must be ordered, got {domT.ords}")
        return T

    @handles(ir.EnumLit)
    def _(self, node: ir.EnumLit):
        # Visit children (just the type)
        T, = self.visit_children(node)
        # Verify type is EnumT
        if not _is_kind(T, ir.EnumT):
            raise TypeError(f"EnumLit must have EnumT type, got {node.T}")
        # Verify label is in the enum
        enumT = _get_T(T)
        if node.label not in enumT.labels:
            raise TypeError(f"EnumLit label '{node.label}' not in enum labels {enumT.labels}")
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
        domainT = _get_T(domainT)
        if not domainT.fin:
            raise TypeError(f"Card expects finite domain, got {domainT}")
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
        domainT = _get_T(domainT)
        # Verify value argument type matches domain carrier type
        if not _is_same_kind(valT, domainT.carT):
            raise TypeError(f"IsMember value type {valT} does not match domain carrier type {domainT.carT}")
        return T

    @handles(ir.CartProd)
    def _(self, node: ir.CartProd):
        T, *domTs = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"CartProd must have DomT type, got {node.T}")
        # Verify all arguments are domains
        prod_domT = _get_T(T)
        for i, domT in enumerate(domTs):
            if not _is_kind(domT, ir.DomT):
                raise TypeError(f"CartProd argument {i} must be a domain, got {domT}")
        for i, (domT, factorT) in enumerate(zip(domTs, prod_domT.factors)):
            domT = _get_T(domT)
            if not _is_same_kind(domT.carT, factorT):
                raise TypeError(f"CartProd argument {i} type {domT} does not match domain factor type {factorT}")
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
        domproj_domT = _get_T(T)
        domT = _get_T(domT)
        if node.idx >= len(domT.factors):
            raise TypeError(f"DomProj index {node.idx} out of bounds for tuple of length {len(domT.factors)}")
        if not _is_same_kind(domproj_domT.carT, domT.factors[node.idx]):
            raise TypeError(f"DomProj result type {node.T} does not match domain factor type {domT.factors[node.idx]}")
        if domproj_domT.fin != domT.fins[node.idx]:
            raise TypeError(f"DomProj result domain must be finite, got {domproj_domT.fin}")
        if domproj_domT.ord != domT.ords[node.idx]:
            raise TypeError(f"DomProj result domain must be ordered, got {domproj_domT.ord}")
        return T

    @handles(ir.TupleLit)
    def _(self, node: ir.TupleLit):
        T, *valTs = self.visit_children(node)
        # Verify type is TupleT
        if not _is_kind(T, ir.TupleT):
            raise TypeError(f"TupleLit must have TupleT type, got {T}")
        # Verify all value arguments match tuple element types
        tupleT = _get_T(T)
        if len(valTs) != len(tupleT.elemTs):
            raise TypeError(f"TupleLit has {len(valTs)} values ({valTs}) but type has {len(tupleT.elemTs)} elements ({tupleT.elemTs})")
        for i, (valT, elemT) in enumerate(zip(valTs, tupleT.elemTs)):
            if not _is_same_kind(valT, elemT):
                raise TypeError(f"TupleLit value {i} type {valT} does not match tuple element type {elemT}")
        return T

    @handles(ir.Proj)
    def _(self, node: ir.Proj):
        T, tupT = self.visit_children(node)
        # Verify tuple argument is a Value with TupleT type
        if not _is_kind(tupT, ir.TupleT):
            raise TypeError(f"Proj expects tuple argument, got {tupT}")
        tupT = _get_T(tupT)
        if node.idx >= len(tupT.elemTs):
            raise TypeError(f"Proj index {node.idx} out of bounds for tuple of length {len(tupT.elemTs)}")
        # Verify result type matches projected element type
        if not _is_same_kind(T, tupT.elemTs[node.idx]):
            raise TypeError(f"Proj result type {node.T} does not match tuple element type {tupT.elemTs[node.idx]}")
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
        disjunion_T = _get_T(T)
        if not _is_kind(disjunion_T.carT, ir.SumT):
            raise TypeError(f"DisjUnion must have sum carrier type, got {disjunion_T.carT}")
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
        dominj_domT = _get_T(T)
        if not _is_kind(dominj_domT.carT, ir.SumT):
            raise TypeError(f"DomInj must have sum carrier type, got {dominj_domT.carT}")
        dominj_carT = _get_T(dominj_domT.carT)
        if node.idx >= len(dominj_carT.elemTs):
            raise TypeError(f"DomInj index {node.idx} out of bounds for sum of length {len(dominj_carT.elemTs)}")
        domT_carT = _get_T(_get_T(domT).carT)
        if not _is_same_kind(dominj_carT.elemTs[node.idx], domT_carT):
            raise TypeError(f"DomInj's result carT {dominj_carT.elemTs[node.idx]} does not match domain carT {domT_carT}")
        return T

    @handles(ir.Inj)
    def _(self, node: ir.Inj):
        T, valT = self.visit_children(node)
        if not _is_kind(T, ir.SumT):
            raise TypeError(f"Inj must have SumT type, got {T}")
        inj_sumT = _get_T(T)
        if node.idx >= len(inj_sumT.elemTs):
            raise TypeError(f"Inj index {node.idx} out of bounds for sum of length {len(inj_sumT.elemTs)}")
        if not _is_same_kind(valT, inj_sumT.elemTs[node.idx]):
            raise TypeError(f"Inj's value type {valT} does not match sum element type {inj_sumT.elemTs[node.idx]} of sum {inj_sumT}")
        return T

    @handles(ir.Match)
    def _(self, node: ir.Match):
        T, scrutT, branchesT = self.visit_children(node)
        # Verify scrutinee is a Value with SumT type
        if not _is_kind(scrutT, ir.SumT):
            raise TypeError(f"Match scrutinee must be SumT, got {scrutT}")
        # Verify branches is a Value with TupleT type
        if not _is_kind(branchesT, ir.TupleT):
            raise TypeError(f"Match branches must be TupleT, got {branchesT}")
        branchesT = _get_T(branchesT)
        scrutT = _get_T(scrutT)
        match_T = _get_T(T)
        if len(branchesT.elemTs) != len(scrutT.elemTs):
            raise TypeError(f"Match branches count {len(branchesT.elemTs)} does not match sum type count {len(scrutT.elemTs)}")
        for i, (sum_elem_T, branch_T) in enumerate(zip(scrutT.elemTs, branchesT.elemTs)):
            if not _is_kind(branch_T, (ir.LambdaT, ir._LambdaTPlaceholder)):
                raise TypeError(f"Match branch {i} must be lambdaT matching sum component {sum_elem_T} to match result type {T}. Got {branch_T}")
            # Verify branch argument type matches sum component
            branch_T = _get_T(branch_T)
            if not _is_same_kind(branch_T.argT, sum_elem_T):
                raise TypeError(f"Match branch {i} argument type {branch_T.argT} does not match sum component {sum_elem_T}")
            if not _is_same_kind(branch_T.retT, match_T):
                raise TypeError(f"Match branch {i} result type {branch_T.retT} does not match match result type {match_T}")
        return T

    @handles(ir.Restrict)
    def _(self, node: ir.Restrict):
        T, domainT, predT = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"Restrict must have DomT type, got {T}")
        # Verify domain argument is a domain
        if not _is_kind(domainT, ir.DomT):
            raise TypeError(f"Restrict expects domain argument, got {domainT}")
        domainT = _get_T(domainT)
        predT = _get_T(predT)
        restrict_T = _get_T(T)
        # Verify predicate is a LambdaT
        if not _is_kind(predT, (ir.LambdaT, ir._LambdaTPlaceholder)):
            raise TypeError(f"Restrict expects LambdaT predicate, got {predT}")
        if not _is_same_kind(predT.argT, domainT.carT):
            raise TypeError(f"Restrict predicate argument type {predT.argT} does not match domain carrier type {domainT.carT}")
        if not _is_kind(predT.retT, ir.BoolT):
            raise TypeError(f"Restrict predicate must return Bool, got {predT.resT}")
        if not _is_same_kind(restrict_T.carT, domainT.carT):
            raise TypeError(f"Restrict result carrier type {restrict_T.carT} does not match domain carrier type {domainT.carT}")
        return T

    @handles(ir.Forall)
    def _(self, node: ir.Forall):
        T, domainT, funT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Forall must have BoolT type, got {T}")
        # Verify domain argument is a domain
        if not _is_kind(domainT, ir.DomT):
            raise TypeError(f"Forall expects domain argument, got {domainT}")
        # Verify function is a LambdaT
        if not _is_kind(funT, (ir.LambdaT, ir._LambdaTPlaceholder)):
            raise TypeError(f"Forall expects LambdaT function, got {funT}")
        domainT = _get_T(domainT)
        funT = _get_T(funT)
        if not _is_same_kind(funT.argT, domainT.carT):
            raise TypeError(f"Forall function argument type {funT.argT} does not match domain carrier type {domainT.carT}")
        if not _is_kind(funT.retT, ir.BoolT):
            raise TypeError(f"Forall function must return Bool, got {funT.retT}")
        return T

    @handles(ir.Exists)
    def _(self, node: ir.Exists):
        T, domainT, funT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"Exists must have BoolT type, got {T}")
        # Verify domain argument is a domain
        if not _is_kind(domainT, ir.DomT):
            raise TypeError(f"Exists expects domain argument, got {domainT}")
        # Verify function is a LambdaT
        if not _is_kind(funT, ir.LambdaT):
            raise TypeError(f"Exists expects LambdaT function, got {funT}")
        funT = _get_T(funT)
        domainT = _get_T(domainT)
        if not _is_same_kind(funT.argT, domainT.carT):
            raise TypeError(f"Exists function argument type {funT.argT} does not match domain carrier type {domainT.carT}")
        if not _is_same_kind(funT.retT, ir.BoolT):
            raise TypeError(f"Exists function must return Bool, got {funT.retT}")
        return T

    @handles(ir.Map)
    def _(self, node: ir.Map):
        T, domT, funT = self.visit_children(node)
        # Verify type is piT
        if not _is_kind(T, ir.PiT):
            raise TypeError(f"Map must have PiT type, got {T}")
        # Verify domain argument is a domain
        if not _is_kind(domT, ir.DomT):
            raise TypeError(f"Map expects domain argument, got {domT}")
        # Verify function is a LambdaT
        if not _is_kind(funT, (ir.LambdaT, ir._LambdaTPlaceholder)):
            raise TypeError(f"Map expects LambdaT function, got {funT}")
        domT = _get_T(domT)
        funT = _get_T(funT)
        mapT = _get_T(T)
        if not _is_same_kind(funT.argT, domT.carT):
            raise TypeError(f"Map function argument type {funT.argT} does not match domain carrier type {domT.carT}")
        mapT_lamT = _get_T(mapT.lam)
        if not _is_same_kind(mapT_lamT.retT, funT.retT):
            raise TypeError(f"Map result type {mapT_lamT.retT} does not match function result type {funT.retT}")
        return T

    @handles(ir.Image)
    def _(self, node: ir.Image):
        raise NotImplementedError("Image not implemented")
        _, funcT = self.visit_children(node)
        # Verify type is DomT
        if not isinstance(node.T, ir.DomT):
            raise TypeError(f"Image must have DomT type, got {node.T}")
        # Verify function argument is a Value with FuncT type
        if not isinstance(funcT, ir.PiT):
            raise TypeError(f"Image expects FuncT argument, got {funcT}")
        if not node.T.eq(funcT.retT):
            raise TypeError(f"Image result type {node.T} does not match function result type {funcT.retT}")
        return node.T

    @handles(ir.Domain)
    def _(self, node: ir.Domain):
        T, piT = self.visit_children(node)
        # Verify type is DomT
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"Domain must have DomT type, got {T}")
        if not _is_kind(piT, ir.PiT):
            raise TypeError(f"Domain expects PiT argument, got {piT}")
        return T

    @handles(ir.Apply)
    def _(self, node: ir.Apply):
        T, piT, argT = self.visit_children(node)
        # Verify function argument is a PiT
        if not _is_kind(piT, ir.PiT):
            raise TypeError(f"Apply expects PiT function, got {piT}")
        piT = _get_T(piT)
        piT_domT = _get_T(piT.dom.T)
        # Verify argument type matches function domain carrier type
        if not _is_same_kind(argT, piT_domT.carT):
            raise TypeError(f"Apply argument type {argT} does not match function domain carrier type {piT_domT.carT}")
        # Verify result type matches function result type
        piT_lamT = _get_T(piT.lam)
        if not _is_same_kind(T, piT_lamT.retT):
            raise TypeError(f"Apply result type {T} does not match function result type {piT_lamT.retT}")
        return T

    @handles(ir.ListLit)
    def _(self, node: ir.ListLit):
        T, valTs = self.visit_children(node)
        # Verify type is FuncT
        if not _is_kind(T, ir.PiT):
            raise TypeError(f"ListLit must have PiT type, got {T}")
        # Verify all value arguments have same type
        if len(valTs) == 0:
            raise NotImplementedError("Cannot type check empty list literal")
        elemT0 = _get_T(valTs[0])
        for i, valT in enumerate(valTs):
            if not _is_same_kind(valT, elemT0):
                raise TypeError(f"ListLit has heterogeneous elements: element 0 is {elemT0}, element {i} is {valT}")
        # Verify list domain construction matches PiT
        piT = _get_T(T)
        piT_domT = _get_T(piT.dom)
        if not _is_same_kind(piT_domT.carT, ir.IntT()):
            raise TypeError(f"ListLit domain type {piT_domT.carT} does not match expected type {ir.IntT()}")
        piT_lamT = _get_T(piT.lam)
        if not _is_same_kind(piT_lamT.retT, elemT0):
            raise TypeError(f"ListLit result type {piT_lamT.retT} does not match first element type {elemT0}")
        return T

    @handles(ir.Fold)
    def _(self, node: ir.Fold):
        raise NotImplementedError("Fold not implemented")
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
        domT = _get_T(domT)
        sliceT = _get_T(T)
        if not _is_same_kind(domT.carT, sliceT.carT):
            raise TypeError(f"Slice result type {sliceT.carT} does not match domain carrier type {domT.carT}")
        return node.T

    @handles(ir.Index)
    def _(self, node: ir.Index):
        T, domT, idxT = self.visit_children(node)
        # Verify domain argument is a domain
        if not _is_kind(domT, ir.DomT):
            raise TypeError(f"Index expects domain argument, got {domT}")
        domT = _get_T(domT)
        if not _is_same_kind(idxT, domT.carT):
            raise TypeError(f"Index idx type {idxT} does not match domain carrier type {domT.carT}")
        # Index only works on rank 1 domains
        if domT.rank != 1:
            raise TypeError(f"Index only works on rank 1 domains, got {domT.rank}")
        if not _is_kind(T, ir.DomT):
            raise TypeError(f"Index result type {T} must be a domain, got {T}")
        indexT = _get_T(T)
        if not _is_same_kind(indexT.carT, domT.factors[domT.axes[0]]):
            raise TypeError(f"Index result domain factor type {indexT.carT} does not match domain factor type {domT.factors[domT.axes[0]]}")
        if indexT.fin != domT.fins[domT.axes[0]]:
            raise TypeError(f"Index result domain must be finite, got {indexT.fin} != {domT.fins[domT.axes[0]]}")
        if indexT.ord != domT.ords[domT.axes[0]]:
            raise TypeError(f"Index result domain must be ordered, got {indexT.ord} != {domT.ords[domT.axes[0]]}")
        return T

    ##############################
    ## Surface-level IR nodes (Used for analysis, but can be collapsed)
    ##############################

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
        return node.T

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
        return T

    @handles(ir.SumReduce)
    def _(self, node: ir.SumReduce):
        T, piT = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"SumReduce must have IntT type, got {T}")
        # Verify function argument is a PiT
        if not _is_kind(piT, ir.PiT):
            raise TypeError(f"SumReduce expects PiT argument, got {piT}")
        piT_lamT = _get_T(_get_T(piT).lam)
        if not _is_kind(piT_lamT.retT, ir.IntT):
            raise TypeError(f"SumReduce expects PiT with Int result type, got {piT_lamT.retT}")
        return T

    @handles(ir.ProdReduce)
    def _(self, node: ir.ProdReduce):
        T, piT = self.visit_children(node)
        # Verify type is IntT
        if not _is_kind(T, ir.IntT):
            raise TypeError(f"ProdReduce must have IntT type, got {T}")
        # Verify function argument is a Value with PiT   type
        if not _is_kind(piT, ir.PiT):
            raise TypeError(f"ProdReduce expects PiT argument, got {piT}")
        piT_lamT = _get_T(_get_T(piT).lam)
        if not _is_same_kind(piT_lamT.retT, ir.IntT):
            raise TypeError(f"ProdReduce expects PiT with Int result type, got {piT_lamT.retT}")
        return T

    @handles(ir.AllDistinct)
    def _(self, node: ir.AllDistinct):
        T, piT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"AllDistinct must have BoolT type, got {T}")
        # Verify function argument is a Value with FuncT type
        if not _is_kind(piT, ir.PiT):
            raise TypeError(f"AllDistinct expects PiT argument, got {piT}")
        return T

    @handles(ir.AllSame)
    def _(self, node: ir.AllSame):
        T, piT = self.visit_children(node)
        # Verify type is BoolT
        if not _is_kind(T, ir.BoolT):
            raise TypeError(f"AllSame must have BoolT type, got {T}")
        # Verify function argument is a Value with PiT type
        if not _is_kind(piT, ir.PiT):
            raise TypeError(f"AllSame expects PiT argument, got {piT}")
        return T

    ##############################
    ## Constructor-level IR nodes (Used for construction but immediately gets transformed for spec)
    ##############################

    @handles(ir._BoundVarPlaceholder)
    def _(self, node: ir._BoundVarPlaceholder):
        T, = self.visit_children(node)
        return T

    @handles(ir._LambdaPlaceholder)
    def _(self, node: ir._LambdaPlaceholder):
        T, boundVarT, bodyT = self.visit_children(node)
        # Verify type is LambdaT
        if not _is_kind(T, (ir.LambdaT, ir._LambdaTPlaceholder)):
            raise TypeError(f"_LambdaPlaceholder must have LambdaT type, got {T}")
        lamT = _get_T(T)
        if not _is_same_kind(boundVarT, lamT.argT):
            raise TypeError(f"_LambdaPlaceholder bound variable type {boundVarT} does not match LambdaT argument type {lamT.argT}")
        if not _is_same_kind(bodyT, lamT.retT):
            raise TypeError(f"_LambdaPlaceholder body type {bodyT} does not match LambdaT result type {lamT.retT}")
        return T
    
    @handles(ir._LambdaTPlaceholder)
    def _(self, node: ir._LambdaTPlaceholder):
        bv_T, retT = self.visit_children(node)
        if not _is_type(retT):
            raise TypeError(f"_LambdaTPlaceholder return type {retT} must be a type")
        if not _is_type(bv_T):
            raise TypeError(f"_LambdaTPlaceholder bound variable type {bv_T} must be a type")
        return node

    @handles(ir._VarPlaceholder)
    def _(self, node: ir._VarPlaceholder):
        T, = self.visit_children(node)
        return T
