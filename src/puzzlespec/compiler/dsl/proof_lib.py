# Infra for witnesses and obligations
# Obligation: requirements on the inputs of an operation
# Witness: A proof object produced by an operation
# Note, Types are just a static 'witness'
from __future__ import annotations
from functools import singledispatch
from dataclasses import dataclass, field
import typing as tp

from . import ir, ir_types as irT


## Obligations
@dataclass(kw_only=True)
class Obligation:
    origin: ir.Node # Origin node of the obligation
    proven: bool = False

# Obligations on values
@dataclass
class ValObl(Obligation):
    pred_fun: tp.Callable[[irT.Type_], 'ast.BoolExpr']

#### Witnesses
@dataclass(kw_only=True)
class Witness:
    subject: ir.Node # Subject node of this witness

@dataclass
class TypeWit(Witness):
    T: irT.Type_

# All Domains will have an assoicated DomAttrWit
@dataclass
class DomAttrWit(Witness):
    is_finite: bool
    is_ordered: bool

# Domains that can be interpreted as a cartesian product of other domains
# D = D0 x D1 x ...
@dataclass
class CartProdWit(Witness):
    doms: tp.Tuple[ir.Node]

# All Funcs (and base values, interpreted as Func[Unit -> val]) will have an associated Doms 
# Func[D0 -> Func[D1 -> ...]]
@dataclass
class DomsWit(Witness):
    doms: tp.Tuple[ir.Node]

class ProofState:
    def __init__(self, *args: tp.Union[Obligation, Witness]):
        self.obls: tp.Dict[tp.Type[Obligation], tp.List[Obligation]] = {}
        self.wits: tp.Dict[tp.Type[Witness], Witness] = {}
        for arg in args:
            if isinstance(arg, Witness):
                self.add_wit(arg)
            elif isinstance(arg, Obligation):
                self.add_obl(arg)
            else:
                raise ValueError(f"Expected Witness or Obligation, got {type(arg)}")

    def copy(self) -> 'ProofState':
        obls = [obl for obls in self.obls.values() for obl in obls]
        wits = list(self.wits.values())
        return ProofState(*obls, *wits)

    def __add__(self, ps: ProofState) -> 'ProofState':
        assert isinstance(ps, ProofState)
        new_ps = self.copy()
        for obls in self.obls.values():
            for obl in obls:
                new_ps.add_obl(obl)
        for wit in self.wits.values():
            new_ps.add_wit(wit)
        return new_ps

    def add_obl(self, obl: Obligation):
        self.obls.setdefault(type(obl),[]).append(obl)

    def add_wit(self, wit: Witness):
        kind = type(wit)
        if kind in self.wits:
            if wit != self.wits[kind]:
                raise NotImplementedError(f"{wit} != {self.wits[kind]}")
        else:
            self.wits[kind] = wit

    def get_obl(self, kind: tp.Type[Obligation]):
        return self.obls.get(kind, None)

    def get_wit(self, kind: tp.Type[Witness]):
        return self.wits.get(kind, None)

    @property
    def T(self):
        wit = self.get_wit(TypeWit)
        if wit is None:
            raise ValueError("No Type found")
        return wit.T

@singledispatch
def _inference(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]) -> ProofState:
    raise NotImplementedError(f"Need to implement inference for {node}")

# Run inference on a node. This will populate the proof state for the node in the penv
def inference(node: ir.Node, penv: tp.Dict[ir.Node, ProofState]={}):
    # Check if the node is already in the penv
    if node in penv:
        return penv
    # Verify that children have proof states
    for child in node._children:
        inference(child, penv)
        #if child not in penv:
        #    raise ValueError(f"Child {child} of {node} has no proof state in penv")
    ps = _inference(node, penv)
    if node in penv:
        penv[node] += ps
    else:
        penv[node] = ps
    return penv

from . import inference as inf