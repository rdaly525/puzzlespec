from __future__ import annotations

import typing as tp

from ..pass_base import Transform, Context, handles
from ...dsl import ir, ir_types as irT
from ..analyses.type_inference import TypeEnv_
from ..analyses.roles import RoleEnv_


class ConcretizeVarsPass(Transform):
    """Concretize symbolic collection variables declared via VarList / VarDict.

    - VarList(size, name) => List(Lit n, FreeVar(name_0), ..., FreeVar(name_{n-1}))
    - VarDict(keys, name) => Dict(k0, FreeVar(name_0), k1, FreeVar(name_1), ...)

    Also updates the `TypeEnv` with entries for each concretized element.

    By default, removes the aggregate name from the TypeEnv to avoid ambiguity
    (`drop_aggregate=True`). Set `drop_aggregate=False` to retain it.
    """

    requires = (TypeEnv_, RoleEnv_,)
    produces: tp.Tuple[type, ...] = ()
    name = "concretize_vars"

    def __init__(self, drop_aggregate: bool = True) -> None:
        super().__init__()
        self.drop_aggregate = drop_aggregate

    def run(self, root: ir.Node, ctx: Context) -> ir.Node:
        self.tenv = tp.cast(TypeEnv_, ctx.get(TypeEnv_)).env
        self.renv = tp.cast(RoleEnv_, ctx.get(RoleEnv_)).env
        return self.visit(root)

    @handles(ir.VarList)
    def _(self, node: ir.VarList) -> ir.Node:
        # Visit size first to allow upstream concretizations
        size = self.visit(node._children[0])
        name = node.name

        if isinstance(size, ir.Lit) and isinstance(size.value, int):
            n = size.value
            if n < 0:
                # Invalid negative length; leave as-is
                return node if (size is node._children[0]) else ir.VarList(size, name)
            # Determine element type from TypeEnv
            listT = self.tenv.vars.get(name)
            if not isinstance(listT, irT.ListT):
                # If type is missing or not a list, leave node intact
                return node if (size is node._children[0]) else ir.VarList(size, name)
            elemT = listT.elemT
            # Inherit role for new names
            role = self.renv.roles.get(name, "decision")

            elems: tp.List[ir.Node] = []
            for i in range(n):
                vname = f"{name}_{i}"
                # Update type env for new var names if not present
                if vname not in self.tenv.vars:
                    self.tenv.vars[vname] = elemT
                self.renv.add(vname, role)
                elems.append(ir.FreeVar(vname))

            # Optionally remove aggregate variable from env
            if self.drop_aggregate and name in self.tenv.vars:
                try:
                    del self.tenv.vars[name]
                except Exception:
                    pass
            if self.drop_aggregate and name in self.renv.roles:
                try:
                    del self.renv.roles[name]
                except Exception:
                    pass

            return ir.List(ir.Lit(n), *elems)

        # No concretization; rebuild if child changed
        return node if (size is node._children[0]) else ir.VarList(size, name)

    @handles(ir.VarDict)
    def _(self, node: ir.VarDict) -> ir.Node:
        # Visit keys first to allow upstream concretizations
        keys = self.visit(node._children[0])
        name = node.name

        if isinstance(keys, ir.List):
            # Determine value type from TypeEnv
            dictT = self.tenv.vars.get(name)
            if not isinstance(dictT, irT.DictT):
                return node if (keys is node._children[0]) else ir.VarDict(keys, name)
            valT = dictT.valT
            role = self.renv.roles.get(name, "decision")

            flat: tp.List[ir.Node] = []
            for i, k in enumerate(keys._children[1:]):
                vname = f"{name}_{i}"
                if vname not in self.tenv.vars:
                    self.tenv.vars[vname] = valT
                self.renv.add(vname, role)
                flat.extend([k, ir.FreeVar(vname)])

            if self.drop_aggregate and name in self.tenv.vars:
                try:
                    del self.tenv.vars[name]
                except Exception:
                    pass
            if self.drop_aggregate and name in self.renv.roles:
                try:
                    del self.renv.roles[name]
                except Exception:
                    pass

            return ir.Dict(*flat)

        return node if (keys is node._children[0]) else ir.VarDict(keys, name)


