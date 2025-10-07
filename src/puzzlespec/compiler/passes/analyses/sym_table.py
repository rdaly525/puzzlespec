from __future__ import annotations
import typing
from ..pass_base import Analysis, AnalysisObject, Context

if typing.TYPE_CHECKING:
    from ...dsl import spec

class SymTableEnv_(AnalysisObject):
    def __init__(self, sym: spec.SymTable):
        self.sym = sym
