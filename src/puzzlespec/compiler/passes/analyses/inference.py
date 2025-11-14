from __future__ import annotations

from re import A
import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ..envobj import EnvsObj
from ...dsl import ir, ir_types as irT
from ...dsl.envs import DomEnv
from ...dsl import proof_lib as pf

class ProofResults(AnalysisObject):
    def __init__(self, penv: tp.Dict[ir.Node, pf.ProofState]):
        self.penv = penv

class InferencePass(Analysis):
    requires = (EnvsObj,)
    produces = (ProofResults,)

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.domenv: DomEnv = ctx.get(EnvsObj).domenv
        self.penv = {}
        self.visit(root)
        return ProofResults(self.penv)

    def visit(self, node: ir.Node):
        self.visit_children(node)
        pf.inference(node, self.penv)

    @handles(ir.VarRef)
    def _(self, node: ir.VarRef):
        doms = self.domenv.get_doms(node.sid)
        for dom in doms:
            self.visit(dom)
        def _T(doms):
            if len(doms)==1:
                return self.penv[doms[0]].T.carT
            else:
                return irT.FuncT(self.penv[doms[0]].T, _T(doms[1:]))
        T = _T(doms)
        self.penv[node] = pf.ProofState(
            pf.DomsWit(doms=doms, subject=node),
            pf.TypeWit(T=T, subject=node)
        )