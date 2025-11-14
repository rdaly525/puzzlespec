from math import e
from . import proof_lib as pf
from . import ir, ir_types as irT
import typing as tp

def children_proof_state(node: ir.Node, penv: tp.Dict[ir.Node, pf.ProofState]):
    proofs = tuple(penv.get(c, None) for c in node._children)
    if None in proofs:
        raise ValueError(f"Missing ProofState for {node}")
    return proofs

def _check_func_child(func_node: ir.Node, func_ps: pf.ProofState, node_name: str) -> pf.DomsWit:
    """Check that a child is a FuncT and has DomsWit. Returns the DomsWit."""
    func_T = func_ps.T
    if not isinstance(func_T, irT.FuncT):
        raise TypeError(f"{node_name} expects FuncT, got {func_T}")
    func_doms_wit = func_ps.get_wit(pf.DomsWit)
    if not func_doms_wit:
        raise TypeError(f"{node_name} expects Func child to have DomsWit, got {func_node}")
    return func_doms_wit

def _check_domain_ordered_finite(dom_node: ir.Node, dom_ps: pf.ProofState, node_name: str) -> None:
    """Check that a domain is ordered and finite."""
    dom_attr_wit = dom_ps.get_wit(pf.DomAttrWit)
    if not dom_attr_wit:
        raise TypeError(f"{node_name} expects domain to have DomAttrWit, got {dom_node}")
    if not dom_attr_wit.is_ordered:
        raise TypeError(f"{node_name} expects domain to be ordered, got {dom_node}")
    if not dom_attr_wit.is_finite:
        raise TypeError(f"{node_name} expects domain to be finite, got {dom_node}")

def _check_func_with_ordered_finite_domain(func_node: ir.Node, func_ps: pf.ProofState, 
                                         penv: tp.Dict[ir.Node, pf.ProofState], 
                                         node_name: str) -> pf.DomsWit:
    """Check Func child and that its domain is ordered and finite. Returns DomsWit."""
    func_doms_wit = _check_func_child(func_node, func_ps, node_name)
    dom_node = func_doms_wit.doms[0]
    dom_ps = penv[dom_node]
    _check_domain_ordered_finite(dom_node, dom_ps, node_name)
    return func_doms_wit

##############################
## Core-level IR nodes (Used throughout entire compiler flow)
##############################

@pf._inference.register(ir.Unit)
def inference_Unit(node: ir.Unit, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    ps = pf.ProofState()
    ps.add_wit(pf.TypeWit(subject=node, T=irT.UnitType))
    return ps

@pf._inference.register(ir.BoundVar)
def inference_BoundVar(node: ir.BoundVar, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    # BoundVar types come from bound variable context, handled in the analysis pass
    # This should not be called directly, but we need to handle it
    raise NotImplementedError("BoundVar inference should be handled in the analysis pass with bound variable context")

@pf._inference.register(ir.Lambda)
def inference_Lambda(node: ir.Lambda, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    body_node, = node._children
    body_ps, = children_proof_state(node, penv)
    lambda_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    # (None - body type is already checked)
    
    # Add witnesses for Lambda
    body_T = body_ps.T
    lambda_ps.add_wit(pf.TypeWit(subject=node, T=irT.ArrowT(node.paramT, body_T)))
    return lambda_ps

@pf._inference.register(ir.Lit)
def inference_Lit(node: ir.Lit, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    ps = pf.ProofState()
    ps.add_wit(pf.TypeWit(subject=node, T=node.T))
    return ps

@pf._inference.register(ir.Eq)
def inference_Eq(node: ir.Eq, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, b_node = node._children
    a_ps, b_ps = children_proof_state(node, penv)
    eq_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    b_T = b_ps.T
    if a_T != b_T:
        raise TypeError(f"Eq has children of inconsistent types: {a_T} != {b_T}")
    
    # Add witnesses for Eq
    eq_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return eq_ps

@pf._inference.register(ir.Lt)
def inference_Lt(node: ir.Lt, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, b_node = node._children
    a_ps, b_ps = children_proof_state(node, penv)
    lt_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    b_T = b_ps.T
    if a_T != irT.Int or b_T != irT.Int:
        raise TypeError(f"Lt expects Int operands, got {a_T} and {b_T}")
    
    # Add witnesses for Lt
    lt_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return lt_ps

@pf._inference.register(ir.LtEq)
def inference_LtEq(node: ir.LtEq, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, b_node = node._children
    a_ps, b_ps = children_proof_state(node, penv)
    lteq_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    b_T = b_ps.T
    if a_T != irT.Int or b_T != irT.Int:
        raise TypeError(f"LtEq expects Int operands, got {a_T} and {b_T}")
    
    # Add witnesses for LtEq
    lteq_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return lteq_ps

@pf._inference.register(ir.Ite)
def inference_Ite(node: ir.Ite, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    pred_node, t_node, f_node = node._children
    pred_ps, t_ps, f_ps = children_proof_state(node, penv)
    ite_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    pred_T = pred_ps.T
    if pred_T != irT.Bool:
        raise TypeError(f"Ite predicate must be Bool, got {pred_T}")
    t_T = t_ps.T
    f_T = f_ps.T
    if t_T != f_T:
        raise TypeError(f"Ite branches must have same type: {t_T} != {f_T}")
    
    # Add witnesses for Ite
    ite_ps.add_wit(pf.TypeWit(subject=node, T=t_T))
    return ite_ps

@pf._inference.register(ir.Not)
def inference_Not(node: ir.Not, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, = node._children
    a_ps, = children_proof_state(node, penv)
    not_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    if a_T != irT.Bool:
        raise TypeError(f"Not expects Bool, got {a_T}")
    
    # Add witnesses for Not
    not_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return not_ps

@pf._inference.register(ir.Neg)
def inference_Neg(node: ir.Neg, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, = node._children
    a_ps, = children_proof_state(node, penv)
    neg_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    if a_T != irT.Int:
        raise TypeError(f"Neg expects Int, got {a_T}")
    
    # Add witnesses for Neg
    neg_ps.add_wit(pf.TypeWit(subject=node, T=irT.Int))
    return neg_ps

@pf._inference.register(ir.Div)
def inference_Div(node: ir.Div, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, b_node = node._children
    a_ps, b_ps = children_proof_state(node, penv)
    div_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    b_T = b_ps.T
    if a_T != irT.Int or b_T != irT.Int:
        raise TypeError(f"Div expects Int operands, got {a_T} and {b_T}")
    
    # Add witnesses for Div
    div_ps.add_wit(pf.TypeWit(subject=node, T=irT.Int))
    return div_ps

@pf._inference.register(ir.Mod)
def inference_Mod(node: ir.Mod, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, b_node = node._children
    a_ps, b_ps = children_proof_state(node, penv)
    mod_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    b_T = b_ps.T
    if a_T != irT.Int or b_T != irT.Int:
        raise TypeError(f"Mod expects Int operands, got {a_T} and {b_T}")
    
    # Add witnesses for Mod
    mod_ps.add_wit(pf.TypeWit(subject=node, T=irT.Int))
    return mod_ps

@pf._inference.register(ir.Conj)
def inference_Conj(node: ir.Conj, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    child_ps_list = children_proof_state(node, penv)
    conj_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    for i, (child, child_ps) in enumerate(zip(node._children, child_ps_list)):
        child_T = child_ps.T
        if child_T != irT.Bool:
            raise TypeError(f"Conj child {i} ({child}) must be Bool, got {child_T}")
    
    # Add witnesses for Conj
    conj_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return conj_ps

@pf._inference.register(ir.Disj)
def inference_Disj(node: ir.Disj, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    child_ps_list = children_proof_state(node, penv)
    disj_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    for i, (child, child_ps) in enumerate(zip(node._children, child_ps_list)):
        child_T = child_ps.T
        if child_T != irT.Bool:
            raise TypeError(f"Disj child {i} ({child}) must be Bool, got {child_T}")
    
    # Add witnesses for Disj
    disj_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return disj_ps

@pf._inference.register(ir.Sum)
def inference_Sum(node: ir.Sum, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    child_ps_list = children_proof_state(node, penv)
    sum_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    for i, (child, child_ps) in enumerate(zip(node._children, child_ps_list)):
        child_T = child_ps.T
        if child_T != irT.Int:
            raise TypeError(f"Sum child {i} ({child}) must be Int, got {child_T}")
    
    # Add witnesses for Sum
    sum_ps.add_wit(pf.TypeWit(subject=node, T=irT.Int))
    return sum_ps

@pf._inference.register(ir.Prod)
def inference_Prod(node: ir.Prod, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    child_ps_list = children_proof_state(node, penv)
    prod_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    for i, (child, child_ps) in enumerate(zip(node._children, child_ps_list)):
        child_T = child_ps.T
        if child_T != irT.Int:
            raise TypeError(f"Prod child {i} ({child}) must be Int, got {child_T}")
    
    # Add witnesses for Prod
    prod_ps.add_wit(pf.TypeWit(subject=node, T=irT.Int))
    return prod_ps

@pf._inference.register(ir.Universe)
def inference_Universe(node: ir.Universe, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    universe_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    # (None)
    
    # Add witnesses for Universe
    is_finite = node.T is irT.Bool or node.T is irT.UnitType
    universe_ps.add_wit(pf.DomAttrWit(subject=node, is_finite=is_finite, is_ordered=False))
    universe_ps.add_wit(pf.TypeWit(subject=node, T=irT.DomT(node.T)))
    return universe_ps

@pf._inference.register(ir.Fin)
def inference_Fin(node: ir.Fin, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    n_node, = node._children
    n_ps, = children_proof_state(node, penv)
    fin_ps = pf.ProofState()

    # Check statically dischargeable obligations
    # Type checking
    n_T = n_ps.T
    if n_T != irT.Int:
        raise TypeError(f"In Fin({n_node}): {n_node} must be Int, got {n_T}")

    # Add witnesses for Fin
    fin_ps.add_wit(pf.DomAttrWit(subject=node, is_finite=True, is_ordered=True))
    fin_ps.add_wit(pf.TypeWit(subject=node, T=irT.DomT(irT.Int)))
    return fin_ps

@pf._inference.register(ir.Enum)
def inference_Enum(node: ir.Enum, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    enum_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    # (None)
    
    # Add witnesses for Enum
    enum_ps.add_wit(pf.DomAttrWit(subject=node, is_finite=True, is_ordered=False))
    enum_ps.add_wit(pf.TypeWit(subject=node, T=irT.DomT(node.enumT)))
    return enum_ps

@pf._inference.register(ir.EnumLit)
def inference_EnumLit(node: ir.EnumLit, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    enum_lit_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    # Verify label is in enumT
    if node.label not in node.enumT.labels:
        raise ValueError(f"EnumLit label '{node.label}' not in enum {node.enumT.name} with labels {node.enumT.labels}")
    
    # Add witnesses for EnumLit
    enum_lit_ps.add_wit(pf.TypeWit(subject=node, T=node.enumT))
    return enum_lit_ps

@pf._inference.register(ir.Card)
def inference_Card(node: ir.Card, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    domain_node, = node._children
    domain_ps, = children_proof_state(node, penv)
    card_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    domain_T = domain_ps.T
    if not isinstance(domain_T, irT.DomT):
        raise TypeError(f"Card expects DomT, got {domain_T}")
    
    # Add witnesses for Card
    card_ps.add_wit(pf.TypeWit(subject=node, T=irT.Int))
    return card_ps

@pf._inference.register(ir.IsMember)
def inference_IsMember(node: ir.IsMember, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    domain_node, val_node = node._children
    domain_ps, val_ps = children_proof_state(node, penv)
    is_member_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    domain_T = domain_ps.T
    if not isinstance(domain_T, irT.DomT):
        raise TypeError(f"IsMember expects DomT as first argument, got {domain_T}")
    val_T = val_ps.T
    if val_T != domain_T.carT:
        raise TypeError(f"IsMember value type {val_T} does not match domain carrier type {domain_T.carT}")
    
    # Add witnesses for IsMember
    is_member_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return is_member_ps

@pf._inference.register(ir.CartProd)
def inference_CartProd(node: ir.CartProd, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    dom_ps_list = children_proof_state(node, penv)
    cart_prod_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    dom_Ts = []
    for i, (dom_node, dom_ps) in enumerate(zip(node._children, dom_ps_list)):
        dom_T = dom_ps.T
        if not isinstance(dom_T, irT.DomT):
            raise TypeError(f"CartProd child {i} ({dom_node}) expects DomT, got {dom_T}")
        dom_Ts.append(dom_T)
    
    # Add witnesses for CartProd
    # Create tuple carrier type
    car_Ts = tuple(dom_T.carT for dom_T in dom_Ts)
    car_T = irT.TupleT(*car_Ts) if len(car_Ts) > 1 else car_Ts[0] if len(car_Ts) == 1 else irT.UnitType

    # CartProd is finite if all component domains are finite, ordered if all are ordered
    dom_attr_wits = [dom_ps.get_wit(pf.DomAttrWit) for dom_ps in dom_ps_list]
    if None in dom_attr_wits:
        raise TypeError(f"CartProd expects all component domains to have DomAttrWit")
    is_finite = all(wit.is_finite for wit in dom_attr_wits)
    is_ordered = all(wit.is_ordered for wit in dom_attr_wits)
    cart_prod_ps.add_wit(pf.DomAttrWit(subject=node, is_finite=is_finite, is_ordered=is_ordered))
    cart_prod_ps.add_wit(pf.TypeWit(subject=node, T=irT.DomT(car_T)))
    cart_prod_ps.add_wit(pf.CartProdWit(subject=node, doms=node._children))
    return cart_prod_ps

@pf._inference.register(ir.DomProj)
def inference_DomProj(node: ir.DomProj, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    dom_node, = node._children
    dom_ps, = children_proof_state(node, penv)
    dom_proj_ps = pf.ProofState()

    # Check statically dischargeable obligations
    # Type checking
    if not isinstance(dom_ps.T, irT.DomT):
        raise TypeError(f"Domain of DomProj ({dom_node}) is not a DomT, got {type(dom_ps.T)}")

    prod_wit: pf.CartProdWit = dom_ps.get_wit(pf.CartProdWit)
    if not prod_wit:
        raise TypeError(f"Domain of DomProj ({dom_node}) needs a CartProdWit")
    if node.idx >= len(prod_wit.doms):
        raise ValueError(f"Domain of DomProj ({dom_node}) only has {len(prod_wit.doms)} components but is being projected onto index {node.idx}")

    # Get the type from the projected domain node's proof state
    proj_dom_node = prod_wit.doms[node.idx]
    proj_dom_ps = penv[proj_dom_node]
    proj_dom_T = proj_dom_ps.T
    if not isinstance(proj_dom_T, irT.DomT):
        raise TypeError(f"Projected domain component {node.idx} of DomProj ({dom_node}) is not a DomT, got {type(proj_dom_T)}")

    # Add witnesses for DomProj
    # DomProj inherits attributes from the projected component domain
    proj_dom_attr_wit = proj_dom_ps.get_wit(pf.DomAttrWit)
    if not proj_dom_attr_wit:
        raise TypeError(f"DomProj expects projected domain component {node.idx} to have DomAttrWit")
    dom_proj_ps.add_wit(pf.DomAttrWit(subject=node, is_finite=proj_dom_attr_wit.is_finite, is_ordered=proj_dom_attr_wit.is_ordered))
    dom_proj_ps.add_wit(pf.TypeWit(subject=node, T=proj_dom_T))
    return dom_proj_ps

@pf._inference.register(ir.TupleLit)
def inference_TupleLit(node: ir.TupleLit, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    val_ps_list = children_proof_state(node, penv)
    tuple_lit_ps = pf.ProofState()
    
    # Add witnesses for TupleLit
    child_Ts = tuple(child_ps.T for child_ps in val_ps_list)
    tuple_lit_ps.add_wit(pf.TypeWit(subject=node, T=irT.TupleT(*child_Ts)))
    return tuple_lit_ps

@pf._inference.register(ir.Proj)
def inference_Proj(node: ir.Proj, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    tup_node, = node._children
    tup_ps, = children_proof_state(node, penv)
    proj_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    tup_T = tup_ps.T
    if not isinstance(tup_T, irT.TupleT):
        raise TypeError(f"Proj expects TupleT, got {tup_T}")
    if node.idx >= len(tup_T.elemTs):
        raise TypeError(f"Proj index {node.idx} out of bounds for tuple of length {len(tup_T.elemTs)}")
    
    # Add witnesses for Proj
    proj_ps.add_wit(pf.TypeWit(subject=node, T=tup_T.elemTs[node.idx]))
    return proj_ps

@pf._inference.register(ir.DisjUnion)
def inference_DisjUnion(node: ir.DisjUnion, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    dom_ps_list = children_proof_state(node, penv)
    disj_union_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    dom_Ts = []
    for i, (dom_node, dom_ps) in enumerate(zip(node._children, dom_ps_list)):
        dom_T = dom_ps.T
        if not isinstance(dom_T, irT.DomT):
            raise TypeError(f"DisjUnion child {i} ({dom_node}) expects DomT, got {dom_T}")
        dom_Ts.append(dom_T)
    
    # Add witnesses for DisjUnion
    car_Ts = tuple(dom_T.carT for dom_T in dom_Ts)
    car_T = irT.SumT(*car_Ts) if len(car_Ts) > 0 else irT.UnitType
    # DisjUnion is finite if all component domains are finite
    # TODO: Determine if DisjUnion should be considered ordered (depends on ordering of sum type)
    dom_attr_wits = [dom_ps.get_wit(pf.DomAttrWit) for dom_ps in dom_ps_list]
    if None in dom_attr_wits:
        raise TypeError(f"DisjUnion expects all component domains to have DomAttrWit")
    is_finite = all(wit.is_finite for wit in dom_attr_wits)
    is_ordered = all(wit.is_ordered for wit in dom_attr_wits)  # TODO: Verify this is correct for disjoint unions
    disj_union_ps.add_wit(pf.DomAttrWit(subject=node, is_finite=is_finite, is_ordered=is_ordered))
    disj_union_ps.add_wit(pf.TypeWit(subject=node, T=irT.DomT(car_T)))
    return disj_union_ps

@pf._inference.register(ir.DomInj)
def inference_DomInj(node: ir.DomInj, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    dom_node, = node._children
    dom_ps, = children_proof_state(node, penv)
    dom_inj_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    dom_T = dom_ps.T
    if not isinstance(dom_T, irT.DomT):
        raise TypeError(f"DomInj expects DomT, got {dom_T}")
    if not isinstance(dom_T.carT, irT.SumT):
        raise TypeError(f"DomInj expects sum carrier type, got {dom_T.carT}")
    if node.idx >= len(dom_T.carT.elemTs):
        raise TypeError(f"DomInj index {node.idx} out of bounds for sum of length {len(dom_T.carT.elemTs)}")
    if dom_T.carT.elemTs[node.idx] != node.T:
        raise TypeError(f"DomInj type mismatch: expected {dom_T.carT.elemTs[node.idx]}, got {node.T}")
    
    # Add witnesses for DomInj
    # DomInj inherits attributes from the input domain
    dom_attr_wit = dom_ps.get_wit(pf.DomAttrWit)
    if not dom_attr_wit:
        raise TypeError(f"DomInj expects input domain to have DomAttrWit")
    dom_inj_ps.add_wit(pf.DomAttrWit(subject=node, is_finite=dom_attr_wit.is_finite, is_ordered=dom_attr_wit.is_ordered))
    dom_inj_ps.add_wit(pf.TypeWit(subject=node, T=irT.DomT(node.T)))
    return dom_inj_ps

@pf._inference.register(ir.Inj)
def inference_Inj(node: ir.Inj, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    val_node, = node._children
    val_ps, = children_proof_state(node, penv)
    inj_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    val_T = val_ps.T
    if val_T != node.T:
        raise TypeError(f"Inj value type {val_T} does not match node type {node.T}")
    
    # Add witnesses for Inj
    # TODO: This should construct a proper sum type, but we don't know the full sum type from just this node
    inj_ps.add_wit(pf.TypeWit(subject=node, T=irT.SumT(node.T)))
    return inj_ps

@pf._inference.register(ir.Match)
def inference_Match(node: ir.Match, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    scrut_node, branches_node = node._children
    scrut_ps, branches_ps = children_proof_state(node, penv)
    match_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    scrut_T = scrut_ps.T
    if not isinstance(scrut_T, irT.SumT):
        raise TypeError(f"Match scrutinee must be SumT, got {scrut_T}")
    branches_T = branches_ps.T
    if not isinstance(branches_T, irT.TupleT):
        raise TypeError(f"Match branches must be TupleT, got {branches_T}")
    if len(branches_T.elemTs) != len(scrut_T.elemTs):
        raise TypeError(f"Match branches count {len(branches_T.elemTs)} does not match sum type count {len(scrut_T.elemTs)}")
    if len(branches_T.elemTs) == 0:
        raise TypeError("Match must have at least one branch")
    
    # Verify each branch is an ArrowT matching the corresponding sum component
    res_T = None
    for i, (sum_elem_T, branch_T) in enumerate(zip(scrut_T.elemTs, branches_T.elemTs)):
        if not isinstance(branch_T, irT.ArrowT):
            raise TypeError(f"Match branch {i} must be ArrowT, got {branch_T}")
        if branch_T.argT != sum_elem_T:
            raise TypeError(f"Match branch {i} argument type {branch_T.argT} does not match sum component {sum_elem_T}")
        if res_T is None:
            res_T = branch_T.resT
        elif branch_T.resT != res_T:
            raise TypeError(f"Match branches must have same result type: {res_T} != {branch_T.resT}")
    
    # Add witnesses for Match
    match_ps.add_wit(pf.TypeWit(subject=node, T=res_T))
    return match_ps

@pf._inference.register(ir.Restrict)
def inference_Restrict(node: ir.Restrict, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    domain_node, pred_node = node._children
    domain_ps, pred_ps = children_proof_state(node, penv)
    restrict_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    domain_T = domain_ps.T
    if not isinstance(domain_T, irT.DomT):
        raise TypeError(f"Restrict expects DomT as first argument, got {domain_T}")
    pred_T = pred_ps.T
    if not isinstance(pred_T, irT.ArrowT):
        raise TypeError(f"Restrict expects ArrowT as second argument, got {pred_T}")
    if pred_T.argT != domain_T.carT:
        raise TypeError(f"Restrict predicate argument type {pred_T.argT} does not match domain carrier type {domain_T.carT}")
    if pred_T.resT != irT.Bool:
        raise TypeError(f"Restrict predicate must return Bool, got {pred_T.resT}")
    
    # Add witnesses for Restrict
    # Restrict inherits attributes from the input domain
    domain_attr_wit = domain_ps.get_wit(pf.DomAttrWit)
    if not domain_attr_wit:
        raise TypeError(f"Restrict expects input domain to have DomAttrWit")
    restrict_ps.add_wit(pf.DomAttrWit(subject=node, is_finite=domain_attr_wit.is_finite, is_ordered=domain_attr_wit.is_ordered))
    restrict_ps.add_wit(pf.TypeWit(subject=node, T=domain_T))
    return restrict_ps

@pf._inference.register(ir.Forall)
def inference_Forall(node: ir.Forall, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    domain_node, fun_node = node._children
    domain_ps, fun_ps = children_proof_state(node, penv)
    forall_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    domain_T = domain_ps.T
    if not isinstance(domain_T, irT.DomT):
        raise TypeError(f"Forall expects DomT as first argument, got {domain_T}")
    fun_T = fun_ps.T
    if not isinstance(fun_T, irT.ArrowT):
        raise TypeError(f"Forall expects ArrowT as second argument, got {fun_T}")
    if fun_T.argT != domain_T.carT:
        raise TypeError(f"Forall function argument type {fun_T.argT} does not match domain carrier type {domain_T.carT}")
    if fun_T.resT != irT.Bool:
        raise TypeError(f"Forall function must return Bool, got {fun_T.resT}")
    
    # Add witnesses for Forall
    forall_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return forall_ps

@pf._inference.register(ir.Exists)
def inference_Exists(node: ir.Exists, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    domain_node, fun_node = node._children
    domain_ps, fun_ps = children_proof_state(node, penv)
    exists_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    domain_T = domain_ps.T
    if not isinstance(domain_T, irT.DomT):
        raise TypeError(f"Exists expects DomT as first argument, got {domain_T}")
    fun_T = fun_ps.T
    if not isinstance(fun_T, irT.ArrowT):
        raise TypeError(f"Exists expects ArrowT as second argument, got {fun_T}")
    if fun_T.argT != domain_T.carT:
        raise TypeError(f"Exists function argument type {fun_T.argT} does not match domain carrier type {domain_T.carT}")
    if fun_T.resT != irT.Bool:
        raise TypeError(f"Exists function must return Bool, got {fun_T.resT}")
    
    # Add witnesses for Exists
    exists_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return exists_ps

@pf._inference.register(ir.Tabulate)
def inference_Tabulate(node: ir.Tabulate, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    dom_node, fun_node = node._children
    dom_ps, fun_ps = children_proof_state(node, penv)
    tabulate_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    dom_T = dom_ps.T
    if not isinstance(dom_T, irT.DomT):
        raise TypeError(f"Tabulate expects DomT as first argument, got {dom_T}")
    fun_T = fun_ps.T
    if not isinstance(fun_T, irT.ArrowT):
        raise TypeError(f"Tabulate expects ArrowT as second argument, got {fun_T}")
    if fun_T.argT != dom_T.carT:
        raise TypeError(f"Tabulate function argument type {fun_T.argT} does not match domain carrier type {dom_T.carT}")
    
    # Add witnesses for Tabulate
    tabulate_ps.add_wit(pf.TypeWit(subject=node, T=irT.FuncT(dom_T, fun_T.resT)))
    # Every Func has a DomsWit where doms[0] is the domain of the Func
    tabulate_ps.add_wit(pf.DomsWit(subject=node, doms=(dom_node,)))
    return tabulate_ps

@pf._inference.register(ir.DomOf)
def inference_DomOf(node: ir.DomOf, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    func_node, = node._children
    func_ps, = children_proof_state(node, penv)
    dom_of_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    func_doms_wit = _check_func_child(func_node, func_ps, "DomOf")
    func_T = func_ps.T
    
    # Add witnesses for DomOf
    domattr = penv[func_ps.get_wit(pf.DomsWit).doms[0]].get_wit(pf.DomAttrWit)
    dom_of_ps.add_wit(pf.TypeWit(subject=node, T=func_T.domT))
    dom_of_ps.add_wit(domattr) # Kind of stupid. DomOf should probably not be a node
    return dom_of_ps

@pf._inference.register(ir.ImageOf)
def inference_ImageOf(node: ir.ImageOf, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    func_node, = node._children
    func_ps, = children_proof_state(node, penv)
    image_of_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    func_doms_wit = _check_func_child(func_node, func_ps, "ImageOf")
    func_T = func_ps.T
    
    # Add witnesses for ImageOf
    image_of_ps.add_wit(pf.TypeWit(subject=node, T=irT.DomT(func_T.resT)))
    return image_of_ps

@pf._inference.register(ir.Apply)
def inference_Apply(node: ir.Apply, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    func_node, arg_node = node._children
    func_ps, arg_ps = children_proof_state(node, penv)
    apply_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    func_doms_wit = _check_func_child(func_node, func_ps, "Apply")
    func_T = func_ps.T
    arg_T = arg_ps.T
    if arg_T != func_T.domT.carT:
        raise TypeError(f"Apply argument type {arg_T} does not match function domain carrier type {func_T.domT.carT}")
    
    doms = func_doms_wit.doms
    resT = func_T.resT
    if isinstance(resT, irT.FuncT):
        dom, codoms = doms[0], doms[1:]
        apply_ps.add_wit(pf.DomsWit(subject=node, doms=codoms))
    elif isinstance(resT, irT.DomT):
        dom, codom = doms
        apply_ps.add_wit(penv[codom].get_wit(pf.DomAttrWit))
    apply_ps.add_wit(pf.TypeWit(subject=node, T=func_T.resT))
    return apply_ps

@pf._inference.register(ir.ListLit)
def inference_ListLit(node: ir.ListLit, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    val_ps_list = children_proof_state(node, penv)
    list_lit_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    if len(val_ps_list) == 0:
        raise NotImplementedError("Cannot infer type of empty list literal")
    elem_T = val_ps_list[0].T
    for i, val_ps in enumerate(val_ps_list[1:], 1):
        val_T = val_ps.T
        if val_T != elem_T:
            raise TypeError(f"ListLit has heterogeneous elements: element 0 is {elem_T}, element {i} is {val_T}")
    
    
    # Add witnesses for ListLit
    # List[B] is Func(Fin(n) -> B)
    n = len(val_ps_list)
    fin_dom = irT.DomT(irT.Int)
    list_lit_ps.add_wit(pf.TypeWit(subject=node, T=irT.FuncT(fin_dom, elem_T)))
    # Note: ListLit produces a FuncT but we don't have a domain node for Fin(n) since n is a Python int
    # The domain is constructed, so we cannot add DomsWit here
    return list_lit_ps

@pf._inference.register(ir.Fold)
def inference_Fold(node: ir.Fold, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    func_node, fun_node, init_node = node._children
    func_ps, fun_ps, init_ps = children_proof_state(node, penv)
    fold_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    func_doms_wit = _check_func_child(func_node, func_ps, "Fold")
    func_T = func_ps.T
    fun_T = fun_ps.T
    if not isinstance(fun_T, irT.ArrowT):
        raise TypeError(f"Fold expects ArrowT as second argument, got {fun_T}")
    # Fold signature: Seq[A] -> ((A,B) -> B) -> B -> B
    elem_T = func_T.resT
    res_T = fun_T.resT
    if init_ps.T != res_T:
        raise TypeError(f"Fold init type {init_ps.T} does not match function result type {res_T}")
    expected_fun_T = irT.ArrowT(irT.TupleT(elem_T, res_T), res_T)
    if fun_T != expected_fun_T:
        raise TypeError(f"Fold function type {fun_T} does not match expected type {expected_fun_T}")
    
    
    # Add witnesses for Fold
    fold_ps.add_wit(pf.TypeWit(subject=node, T=res_T))
    return fold_ps

##############################
## Surface-level IR nodes (Used for analysis, but can be collapsed)
##############################

@pf._inference.register(ir.And)
def inference_And(node: ir.And, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, b_node = node._children
    a_ps, b_ps = children_proof_state(node, penv)
    and_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    b_T = b_ps.T
    if a_T != irT.Bool or b_T != irT.Bool:
        raise TypeError(f"And expects Bool operands, got {a_T} and {b_T}")
    
    # Add witnesses for And
    and_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return and_ps

@pf._inference.register(ir.Implies)
def inference_Implies(node: ir.Implies, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, b_node = node._children
    a_ps, b_ps = children_proof_state(node, penv)
    implies_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    b_T = b_ps.T
    if a_T != irT.Bool or b_T != irT.Bool:
        raise TypeError(f"Implies expects Bool operands, got {a_T} and {b_T}")
    
    # Add witnesses for Implies
    implies_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return implies_ps

@pf._inference.register(ir.Or)
def inference_Or(node: ir.Or, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, b_node = node._children
    a_ps, b_ps = children_proof_state(node, penv)
    or_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    b_T = b_ps.T
    if a_T != irT.Bool or b_T != irT.Bool:
        raise TypeError(f"Or expects Bool operands, got {a_T} and {b_T}")
    
    # Add witnesses for Or
    or_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return or_ps

@pf._inference.register(ir.Add)
def inference_Add(node: ir.Add, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, b_node = node._children
    a_ps, b_ps = children_proof_state(node, penv)
    add_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    b_T = b_ps.T
    if a_T != irT.Int or b_T != irT.Int:
        raise TypeError(f"Add expects Int operands, got {a_T} and {b_T}")
    
    # Add witnesses for Add
    add_ps.add_wit(pf.TypeWit(subject=node, T=irT.Int))
    return add_ps

@pf._inference.register(ir.Sub)
def inference_Sub(node: ir.Sub, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, b_node = node._children
    a_ps, b_ps = children_proof_state(node, penv)
    sub_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    b_T = b_ps.T
    if a_T != irT.Int or b_T != irT.Int:
        raise TypeError(f"Sub expects Int operands, got {a_T} and {b_T}")
    
    # Add witnesses for Sub
    sub_ps.add_wit(pf.TypeWit(subject=node, T=irT.Int))
    return sub_ps

@pf._inference.register(ir.Mul)
def inference_Mul(node: ir.Mul, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, b_node = node._children
    a_ps, b_ps = children_proof_state(node, penv)
    mul_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    b_T = b_ps.T
    if a_T != irT.Int or b_T != irT.Int:
        raise TypeError(f"Mul expects Int operands, got {a_T} and {b_T}")
    
    # Add witnesses for Mul
    mul_ps.add_wit(pf.TypeWit(subject=node, T=irT.Int))
    return mul_ps

@pf._inference.register(ir.Gt)
def inference_Gt(node: ir.Gt, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, b_node = node._children
    a_ps, b_ps = children_proof_state(node, penv)
    gt_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    b_T = b_ps.T
    if a_T != irT.Int or b_T != irT.Int:
        raise TypeError(f"Gt expects Int operands, got {a_T} and {b_T}")
    
    # Add witnesses for Gt
    gt_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return gt_ps

@pf._inference.register(ir.GtEq)
def inference_GtEq(node: ir.GtEq, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    a_node, b_node = node._children
    a_ps, b_ps = children_proof_state(node, penv)
    gteq_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    a_T = a_ps.T
    b_T = b_ps.T
    if a_T != irT.Int or b_T != irT.Int:
        raise TypeError(f"GtEq expects Int operands, got {a_T} and {b_T}")
    
    # Add witnesses for GtEq
    gteq_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return gteq_ps

@pf._inference.register(ir.Windows)
def inference_Windows(node: ir.Windows, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    dom_node, size_node, stride_node = node._children
    dom_ps, size_ps, stride_ps = children_proof_state(node, penv)
    windows_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    dom_T = dom_ps.T
    _check_domain_ordered_finite(dom_node, dom_ps, 'Windows')
    size_T = size_ps.T
    stride_T = stride_ps.T
    if size_T != irT.Int or stride_T != irT.Int:
        raise TypeError(f"Windows expects Int for size and stride, got {size_T} and {stride_T}")
    
    # Add witnesses for Windows
    # Windows: SeqDom[A] -> Int -> Int -> Func[Fin(n) -> SeqDom[A]]
    T = irT.FuncT(irT.DomT(irT.Int), dom_T)
    windows_ps.add_wit(pf.TypeWit(subject=node, T=T))

    # Construct domain for Windows
    # N = (L - (size-stride))/stride
    # X X X X X X
    # (6, 3, 1) -> 4 
    # (6, 2, 1) -> 5
    # X X X X X X X
    # (7, 3, 2) -> 3
    # (9, 3, 3) -> 3

    L = ir.Card(dom_node)
    N = ir.Div(ir.Sub(L, ir.Sub(size_node, stride_node)), stride_node)
    new_dom = ir.Fin(N)
    penv = pf.inference(new_dom, penv)
    windows_ps.add_wit(pf.DomsWit(subject=node, doms=(new_dom, dom_node)))
    return windows_ps

@pf._inference.register(ir.Tiles)
def inference_Tiles(node: ir.Tiles, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    grid_node, sizes_node, strides_node = node._children
    grid_ps, sizes_ps, strides_ps = children_proof_state(node, penv)
    tiles_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    grid_doms_wit = _check_func_with_ordered_finite_domain(grid_node, grid_ps, penv, "Tiles")
    grid_T = grid_ps.T
    sizes_T = sizes_ps.T
    strides_T = strides_ps.T
    # sizes and strides should be tuples of Ints
    if not isinstance(sizes_T, irT.TupleT):
        raise TypeError(f"Tiles sizes must be TupleT, got {sizes_T}")
    if not isinstance(strides_T, irT.TupleT):
        raise TypeError(f"Tiles strides must be TupleT, got {strides_T}")
    for i, size_elem_T in enumerate(sizes_T.elemTs):
        if size_elem_T != irT.Int:
            raise TypeError(f"Tiles size element {i} must be Int, got {size_elem_T}")
    for i, stride_elem_T in enumerate(strides_T.elemTs):
        if stride_elem_T != irT.Int:
            raise TypeError(f"Tiles stride element {i} must be Int, got {stride_elem_T}")
    
   
    # Add witnesses for Tiles
    # Tiles: GridDom[A] -> (int,...) -> (int,...) -> Func[Fin(r) x Fin(c) -> GridDom[A]]
    elem_T = grid_T.resT
    tile_dom = grid_T.domT  # TODO: This should be the tile domain
    n_tiles_dom = irT.DomT(irT.Int)
    tile_grid_T = irT.FuncT(tile_dom, elem_T)
    tiles_ps.add_wit(pf.TypeWit(subject=node, T=irT.FuncT(n_tiles_dom, tile_grid_T)))
    # Note: Tiles produces a FuncT but the domain n_tiles_dom is constructed, so we cannot add DomsWit here
    return tiles_ps

@pf._inference.register(ir.Slices)
def inference_Slices(node: ir.Slices, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    dom_node, = node._children
    dom_ps, = children_proof_state(node, penv)
    slices_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    dom_T = dom_ps.T
    if not isinstance(dom_T, irT.DomT):
        raise TypeError(f"Slices expects DomT, got {dom_T}")
    cart_wit = dom_ps.get_wit(pf.CartProdWit)
    if cart_wit is None:
        raise TypeError(f"Slices expects CartProdWit, got {dom_T}")
    if node.idx >= len(cart_wit.doms):
        raise TypeError(f"Slices index {node.idx} out of bounds for CartProd with {len(cart_wit.doms)} components")
    
    # Add witnesses for Slices
    doms = cart_wit.doms
    func_dom = doms[node.idx]
    slices_ps.add_wit(pf.DomsWit(subject=node, doms=(func_dom, dom_node)))
    slices_ps.add_wit(pf.TypeWit(subject=node, T=irT.FuncT(penv[func_dom].T, dom_T)))
    return slices_ps

@pf._inference.register(ir.SumReduce)
def inference_SumReduce(node: ir.SumReduce, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    func_node, = node._children
    func_ps, = children_proof_state(node, penv)
    sum_reduce_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    func_doms_wit = _check_func_child(func_node, func_ps, "SumReduce")
    func_T = func_ps.T
    if func_T.resT != irT.Int:
        raise TypeError(f"SumReduce expects FuncT with Int element type, got {func_T.resT}")
    
    # Add witnesses for SumReduce
    sum_reduce_ps.add_wit(pf.TypeWit(subject=node, T=irT.Int))
    return sum_reduce_ps

@pf._inference.register(ir.ProdReduce)
def inference_ProdReduce(node: ir.ProdReduce, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    func_node, = node._children
    func_ps, = children_proof_state(node, penv)
    prod_reduce_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    func_doms_wit = _check_func_child(func_node, func_ps, "ProdReduce")
    func_T = func_ps.T
    if func_T.resT != irT.Int:
        raise TypeError(f"ProdReduce expects FuncT with Int element type, got {func_T.resT}")
    
    # Add witnesses for ProdReduce
    prod_reduce_ps.add_wit(pf.TypeWit(subject=node, T=irT.Int))
    return prod_reduce_ps

@pf._inference.register(ir.AllDistinct)
def inference_AllDistinct(node: ir.AllDistinct, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    func_node, = node._children
    func_ps, = children_proof_state(node, penv)
    distinct_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    func_doms_wit = _check_func_child(func_node, func_ps, "Distinct")
    
    # Add witnesses for Distinct
    distinct_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return distinct_ps

@pf._inference.register(ir.AllSame)
def inference_AllSame(node: ir.AllSame, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    func_node, = node._children
    func_ps, = children_proof_state(node, penv)
    distinct_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    func_doms_wit = _check_func_child(func_node, func_ps, "Distinct")
    
    # Add witnesses for Distinct
    distinct_ps.add_wit(pf.TypeWit(subject=node, T=irT.Bool))
    return distinct_ps


##############################
## Constructor-level IR nodes (Used for construction but immediately gets transformed)
##############################

@pf._inference.register(ir._BoundVarPlaceholder)
def inference_BoundVarPlaceholder(node: ir._BoundVarPlaceholder, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    dom, T = node.dom, node.T
    ps = pf.ProofState(
        pf.DomsWit(subject=node, doms=(dom,)),
        pf.TypeWit(subject=node, T=T)
    )
    return ps

@pf._inference.register(ir._LambdaPlaceholder)
def inference_LambdaPlaceholder(node: ir._LambdaPlaceholder, penv: tp.Dict[ir.Node, pf.ProofState]) -> pf.ProofState:
    bv, body = node._children
    bv_ps, body_ps = children_proof_state(node, penv)
    lam_ps = pf.ProofState()
    
    # Check statically dischargeable obligations
    
    # Add witnesses for Distinct
    lam_ps.add_wit(pf.TypeWit(subject=node, T=irT.ArrowT(bv_ps.T, body_ps.T)))
    return lam_ps

    