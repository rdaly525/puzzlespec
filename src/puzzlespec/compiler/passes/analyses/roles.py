from __future__ import annotations
import typing
from ..pass_base import Analysis, AnalysisObject, Context

if typing.TYPE_CHECKING:
    from ...dsl import spec


class RoleEnv_(AnalysisObject):
    def __init__(self, env: spec.RoleEnv):
        self.env = env


class RolesPass(Analysis):
    """Expose the PuzzleSpec role environment in the pass Context.
    """

    produces = (RoleEnv_,)
    requires = ()
    name = "roles"

    def __init__(self, puzzle_spec: spec.PuzzleSpec):
        super().__init__()
        self._ps = puzzle_spec

    def run(self, root, ctx: Context) -> AnalysisObject:
        return RoleEnv_(self._ps.renv)


