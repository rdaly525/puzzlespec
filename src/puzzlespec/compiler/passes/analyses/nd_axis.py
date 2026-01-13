from __future__ import annotations
from dataclasses import dataclass
import typing as tp
from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir


def get_info(node: ir.Value) -> DomInfo:
    if not isinstance(node.T, ir.DomT):
        raise NotImplementedError()
    ctx = Context()
    return NDDomPass()(node, ctx)

class DomInfo(AnalysisObject):
    def __init__(self, info):
        self.info = info

# Cross product of 3 kinds of domains
# 1) 'sequential domain' Fin(N) OR Image(Fin(N) -> Int) where that is injective
# 2) singleton domain 
# 3) non-ordered domain (like an Enum)

@dataclass
class DomInfo:
    singleton: bool = None
    ord: bool = None
    factors: tp.Tuple[DomInfo] = None

@dataclass
class FuncInfo:
    fin_dom: bool

class NDDomPass(Analysis):
    requires = ()
    produces = (DomInfo,)
    name = "nd_dom"

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        dom_info = self.visit(root)
        return DomInfo(dom_info)

    # High level:
    # Doms should return domino
    # Funcs should return Funcinfo

    @handles(ir.Fin)
    def _(self, node: ir.Fin):
        return DomInfo(ord=True, singleton=False)

    @handles(ir.InjImage)
    def _(self, node: ir.InjImage):
        _, dinfo = self.visit_children(node)
        #dinfo is the info about the map

    @handles(ir.CartProd)
    def _(self, node: ir.CartProd):
        _, *dom_infos = self.visit_children(node)
        return DomInfo(factors=dom_infos)

    @handles(ir.Map)
    def _(self, node: ir.Map):
        _, dinfo, lam = self.visit_children(node)
        return dinfo










# Deprecated and is what I am trying to replace
def _dom_size(dom: ir.dom):
    if not _is_domain(dom):
        raise ValueError(f"Expected domain, got {dom}")
    if isinstance(dom, ir.Universe):
        T: ir.DomT = dom.T
        if not T.fin:
            return None
        else:
            carT: ir.Type = T.carT
            if _is_kind(carT, ir.UnitT):
                return 1
            elif _is_kind(carT, ir.EnumT):
                return len(carT.labels)
            else:
                return None
    if isinstance(dom, ir.RestrictEq):
        _, _, v = dom._children
        if _lit_val(v) is not None:
            return 1
        return None
    if isinstance(dom, ir.Fin):
        return _lit_val(dom._children[1])
    if isinstance(dom, ir.Range):
        lo = _lit_val(dom._children[0])
        hi = _lit_val(dom._children[1])
        if lo is None or hi is None:
            return None
        return hi - lo
    if isinstance(dom, ir.CartProd):
        sizes = tuple(_dom_size(c) for c in dom._children[1:])
        if any(s is None for s in sizes):
            return None
        return ft.reduce(lambda a, b: a * b, sizes, 1)
    if isinstance(dom, ir.DisjUnion):
        sizes = tuple(_dom_size(c) for c in dom._children[1:])
        if any(s is None for s in sizes):
            return None
        return sum(sizes)
    if isinstance(dom, ir.DomLit):
        return len(dom._children[1:])
    return None

# Yields doms or None
def _iterate(dom: ir.Value):
    if not _is_domain(dom):
        raise ValueError(f"Expected domain, got {dom}")
    intT = ir.IntT()
    if isinstance(dom, ir.Universe):
        T: ir.DomT = dom.T
        if not T.fin:
            yield None
        else:
            carT: ir.Type = T.carT
            if _is_kind(carT, ir.UnitT):
                yield ir.Unit(carT)
            elif _is_kind(carT, ir.EnumT):
                for label in carT.labels:
                    yield ir.EnumLit(carT, label)
            else:
                yield None
    elif isinstance(dom, ir.RestrictEq):
        _, _, v = dom._children
        if isinstance(v, ir.Lit):
            yield v
        else:
            yield None
    elif isinstance(dom, ir.Fin):
        n = dom._children[1]
        if not isinstance(n, ir.Lit):
            yield None
        for i in range(n.val):
            yield ir.Lit(intT, val=i)
    elif isinstance(dom, ir.Range):
        lo, hi = dom._children[1:]
        if not isinstance(lo, ir.Lit) or not isinstance(hi, ir.Lit):
            yield None
            return
        for i in range(lo.val, hi.val):
            yield ir.Lit(intT, val=i)
    elif isinstance(dom, ir.CartProd):
        doms = dom._children[1:]
        tupT = None
        for vals in it.product(*[_iterate(edom) for edom in doms]):

            if any(v is None for v in vals):
                yield None
                return
            if tupT is None:
                tupT = ir.TupleT(*(v.T for v in vals))
            yield ir.TupleLit(tupT, *vals)
    elif isinstance(dom, ir.DisjUnion):
        doms = dom._children[1:]
        T = dom.T
        for i, edom in enumerate(doms):
            for v in _iterate(edom):
                if v is None:
                    yield None
                    return
                yield ir.Inj(T.carT, v, i)
    elif isinstance(dom, ir.DomLit):
        for elem in dom._children[1:]:
            yield elem
    else:
        yield None

