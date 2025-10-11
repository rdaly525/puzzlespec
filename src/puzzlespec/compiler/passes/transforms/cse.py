from ..pass_base import Transform, Context, AnalysisObject, handles
from ...dsl import ir, ast
import typing as tp
from dataclasses import dataclass


# All the work is done in the memoization of the pass base
class CSE(Transform):
    requires = ()
    produces = ()
    name = "cse"