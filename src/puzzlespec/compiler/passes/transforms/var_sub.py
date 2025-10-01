from __future__ import annotations

import typing as tp

from ..pass_base import Transform, Context, AnalysisObject, handles
from ...dsl import ir
from ..analyses.roles import RoleEnv_


class VarValues(AnalysisObject):
    def __init__(self, **kwargs):
        # Mapping: var name -> ir.Node | int | bool
        self.mapping: tp.Dict[str, tp.Union[ir.Node, int, bool]] = kwargs


def _to_ir_node(val: tp.Union[ir.Node, int, bool]) -> ir.Node:
    if isinstance(val, ir.Node):
        return val
    if isinstance(val, (int, bool)):
        return ir.Lit(val)
    raise TypeError(f"Unsupported substitution value type: {type(val)}")


class VarSubPass(Transform):
    """Substitute FreeVar occurrences by name using provided values.

    Options:
    - target: 'decision' | 'generator' | 'both' to filter by variable role
    Requires roles via RoleEnv_ and values via VarValues.
    """

    requires = (RoleEnv_, VarValues)
    produces: tp.Tuple[type, ...] = ()
    name = "var_sub"

    def __init__(self, target: str = "both") -> None:
        super().__init__()
        if target not in ("decision", "generator", "both"):
            raise ValueError("target must be 'decision', 'generator', or 'both'")
        self.target = target

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        self.roles = tp.cast(RoleEnv_, ctx.get(RoleEnv_)).env.roles
        self.values = tp.cast(VarValues, ctx.get(VarValues)).mapping
        return self.visit(root)

    @handles(ir.FreeVar)
    def _(self, node: ir.FreeVar) -> ir.Node:
        name = node.name
        role = self.roles.get(name, None)
        # Determine if this var should be targeted
        should = (
            self.target == "both"
            or (self.target == "decision" and role == "decision")
            or (self.target == "generator" and role == "generator")
        )
        if should and name in self.values:
            return _to_ir_node(self.values[name])
        return node


