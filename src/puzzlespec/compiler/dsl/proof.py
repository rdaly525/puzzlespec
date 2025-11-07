# Infra for witnesses and obligations
# Obligation: requirements on the inputs of an operation
# Witness: A proof object produced by an operation
# Note, Types are just a static 'witness'
from __future__ import annotations
from functools import singledispatch
from dataclasses import dataclass, field
from multiprocessing import Value
import typing as tp
from . import ir, ir_types as irT


## Obligations
class Obligation:
    only1: bool=True
    ...

@dataclass
class ValObl(Obligation):
    bool_node: ir.Node
    only1=False

#### Witnesses
class Witness:
    ...

@dataclass
class TypeWit(Witness):
    T: irT.Type_

@dataclass
class FiniteWit(Witness):
    is_finite: bool

@dataclass
class RankWit(Witness):
    rank: int

@dataclass
class OrderedWit(Witness):
    is_ordered: bool

@dataclass
class CartProdWit(Witness):
    doms: tp.Tuple[ir.Node]


class ProofState:
    def __init__(self, *proofs: 'ProofState'):
        self.obls = []
        self.wits = []
        for p in proofs:
            self.obls.extend(p.obls)

    def __iadd__(self, val: tp.Union[Obligation, Witness]) -> tp.Self:
        if isinstance(val, Obligation):
            self.obls.append(val)
        elif isinstance(val, Witness):
            self.wits.append(val)
        return self

    def get_obl(self, kind: tp.Type[Obligation]):
        obls = [obl for obl in self.obls if isinstance(obl, kind)]
        if len(obls)==0:
            return None
        if len(obls)==1 and kind.only1:
            return obls[0]
        if kind.only1:
            raise ValueError(f"Requires only 1 obligation for {kind}, but found {obls}")
        return tuple(obls)

    def get_wit(self, kind: tp.Type[Witness]):
        wits = [wit for wit in self.wits if isinstance(wit, kind)]
        if len(wits)==0:
            return None
        if len(wits)==1:
            return wits[0]
        raise ValueError(f"Requires only 1 witness for {kind}, but found {wits}")

    @property
    def T(self):
        return self.get_wit(TypeWit).T

    def __add__(self, other: ProofState) -> ProofState:
        #TODO: Implement addition of proof states
        ...

def children_proofs(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]):
    proofs = tuple(penv.get(c, None) for c in node._children)
    if None in proofs:
        raise ValueError(f"Missing proof obj for {node}")
    return proofs

# Run inference on a node. This will populate the proof state for the node in the penv
def inference(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> tp.Dict[ir.Node, ProofState]:
    ps = _inference(node, penv)
    penv[node] = ps
    return penv

@singledispatch
def _inference(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> ProofState:
    raise ValueError(f"Need to implement inference for {node}")

@inference.register(ir.Fin)
def inference_Fin(node: ir.Fin, penv: tp.Dict[ir.Node, ProofState]) -> ProofState:
    p_n, = children_proofs(node, penv)

    # Static proofs
    
    # Type checking
    n_T = p_n.T
    if n_T != irT.Int:
        raise ValueError()

    fin_p = ProofState(p_n)
    fin_p += ValObl(ir.Gt(node._children[0], ir.Lit(0)))
    fin_p += FiniteWit(True)
    fin_p += OrderedWit(True)
    fin_p += TypeWit(irT.DomT(irT.Int))
    return fin_p

def inference_DomProj(node: ir.DomProj, penv: tp.Dict[ir.Node, ProofState]):
    dom, = node._children
    dom_p = penv[dom]

    # Type checking
    if not isinstance(dom_p.T, )
    prod_wit = dom_p.get_wit(CartProdWit)
    if not prod_wit:
        raise ValueError(f"Domain of DomProj ({dom}) needs a CartProdWit")
    if len(prod_wit.doms)<dom.idx
    
    domproj_p = ProofState(dom_p)
    
