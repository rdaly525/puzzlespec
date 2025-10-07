from __future__ import annotations
from multiprocessing import Value
from re import T
from ..pass_base import Context, AnalysisObject, Analysis, handles
from ...dsl import ir, ast, ir_types as irT
import typing as tp

if tp.TYPE_CHECKING:
    from ...dsl import spec


class TypeEnv_(AnalysisObject):
    def __init__(self, env: spec.TypeEnv):
        self.env = env

class TypeValues(AnalysisObject):
    def __init__(self, mapping):
        self.mapping: tp.Dict[ir.Node, irT.Type_] = mapping

class TypeInferencePass(Analysis):
    requires = (TypeEnv_,)
    produces = (TypeValues,)
    name = "type_inference"
    def __init__(self):
        super().__init__()

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        # Use concrete mapping for fast lookup
        self.tenv: tp.Dict[int, irT.Type_] = ctx.get(TypeEnv_).env
        self.node_types: tp.Dict[ir.Node, irT.Type_] = {}
        self.bctx = []
        # Walk and populate
        self.visit(root)
        # Package result
        tv = TypeValues(self.node_types)
        ctx.add(tv)
        return root

    # Should not see these because the should have been removed when adding constraint to spec
    @handles(ir._LambdaPlaceholder)
    @handles(ir._BoundVarPlaceholder)
    def _(self, node: ir.Node): 
        raise ValueError("SHOULD NOT BE HERE")

    @handles(ir.VarRef)
    def _(self, var: ir.VarRef):
        assert var.sid in self.tenv
        self.node_types[var] = self.tenv[var.sid]
        return var

    @handles(ir.Lambda)
    def _(self, lam: ir.Lambda):
        self.bctx.append(lam.paramT)
        self.visit_children(lam)
        self.bctx.pop()
        argT = lam.paramT
        resT = self.node_types[lam._children[0]]
        lamT = irT.ArrowT(argT, resT)
        self.node_types[lam] = lamT
        return lam

    @handles(ir.BoundVar)
    def visit_bound_var(self, var: ir.BoundVar):
        assert var.idx < len(self.bctx)
        self.node_types[var] = self.bctx[-(var.idx+1)]
        return var

    @handles(ir.Not, ir.And, ir.Or, ir.Implies, ir.Conj, ir.Disj)
    def visit_bool_op(self, op: ir.Node):
        self.visit_children(op)
        # Check children are bool
        for child in op._children:
            if self.node_types[child] != irT.Bool:
                raise TypeError(f"Child {child} of {op} is not bool")
        self.node_types[op] = irT.Bool
        return op

    # Visit int, int -> int ops
    @handles(ir.Add, ir.Sub, ir.Mul, ir.Div, ir.Mod)
    def visit_int_to_int(self, op: ir.Node):
        self.visit_children(op)
        # Check children are int
        for child in op._children:
            if self.node_types[child] != irT.Int:
                raise TypeError(f"Child {child} of {op} is not int")
        self.node_types[op] = irT.Int
        return op
    
    # Visit int, int -> bool ops
    @handles(ir.Gt, ir.GtEq, ir.Lt, ir.LtEq)
    def visit_int_to_bool(self, op: ir.Node):
        self.visit_children(op)
        # Check children are int
        for child in op._children:
            if self.node_types[child] != irT.Int:
                raise TypeError(f"Child {child} of {op} is not int")
        self.node_types[op] = irT.Bool
        return op

    # Equality
    @handles(ir.Eq)
    def visit_equality(self, op: ir.Node):
        self.visit_children(op)
        # Check children are same type
        for child in op._children:
            if self.node_types[child] != self.node_types[op._children[0]]:
                raise TypeError(f"Child {child} of {op} is not same type as {op._children[0]}")
        self.node_types[op] = irT.Bool
        return op

    # Tuples
    @handles(ir.Tuple)
    def visit_tuple(self, op: ir.Tuple):
        self.visit_children(op)
        self.node_types[op] = irT.TupleT(*(self.node_types[c] for c in op._children))
        return op
    
    # Literals and simple nodes
    @handles(ir.Lit)
    def _(self, node: ir.Lit):
        self.node_types[node] = node.T
        return node

    @handles(ir._Param)
    def _(self, node: ir._Param):
        self.node_types[node] = node.T
        return node

    # Lists
    @handles(ir.List)
    def _(self, node: ir.List):
        # children: (length, elem0, elem1, ...)
        self.visit_children(node)
        if len(node._children) == 0:
            raise TypeError("List literal missing length child")
        length_node = node._children[0]
        if self.node_types[length_node] is not irT.Int:
            raise TypeError("List length must be Int")
        elems = node._children[1:]
        if len(elems) == 0:
            raise TypeError("Cannot infer element type of empty list literal")
        elemT0 = self.node_types[elems[0]]
        for e in elems:
            if self.node_types[e] is not elemT0:
                raise TypeError("Heterogeneous list literal elements")
        self.node_types[node] = irT.ListT(elemT0)
        return node

    @handles(ir.ListTabulate)
    def _(self, node: ir.ListTabulate):
        # size: Int, fun: Int -> V
        self.visit_children(node)
        size, fun = node._children
        if self.node_types[size] is not irT.Int:
            raise TypeError("ListTabulate size must be Int")
        if not isinstance(fun, ir.Lambda):
            raise TypeError("ListTabulate expects a Lambda as second child")
        lamT = self.node_types[fun]
        if lamT.argT is not irT.Int:
            raise TypeError("ListTabulate lambda key must be Int")
        self.node_types[node] = irT.ListT(lamT.resT)
        return node

    @handles(ir.ListGet)
    def _(self, node: ir.ListGet):
        self.visit_children(node)
        lst, idx = node._children
        lstT = self.node_types[lst]
        if not isinstance(lstT, irT.ListT):
            raise TypeError("ListGet expects a list as first operand")
        if self.node_types[idx] is not irT.Int:
            raise TypeError("ListGet index must be Int")
        self.node_types[node] = lstT.elemT
        return node

    @handles(ir.ListLength)
    def _(self, node: ir.ListLength):
        self.visit_children(node)
        lst = node._children[0]
        lstT = self.node_types[lst]
        if not isinstance(lstT, irT.ListT):
            raise TypeError("ListLength expects a list")
        self.node_types[node] = irT.Int
        return node

    @handles(ir.ListWindow)
    def _(self, node: ir.ListWindow):
        self.visit_children(node)
        lst, size, stride = node._children
        if not isinstance(self.node_types[lst], irT.ListT):
            raise TypeError("ListWindow expects a list")
        if self.node_types[size] is not irT.Int or self.node_types[stride] is not irT.Int:
            raise TypeError("ListWindow size and stride must be Int")
        elemT = tp.cast(irT.ListT, self.node_types[lst]).elemT
        self.node_types[node] = irT.ListT(irT.ListT(elemT))
        return node

    @handles(ir.ListConcat)
    def _(self, node: ir.ListConcat):
        self.visit_children(node)
        a, b = node._children
        aT, bT = self.node_types[a], self.node_types[b]
        if not isinstance(aT, irT.ListT) or not isinstance(bT, irT.ListT):
            raise TypeError("ListConcat expects list operands")
        if aT.elemT is not bT.elemT:
            raise TypeError("ListConcat element types must match")
        self.node_types[node] = aT
        return node

    # Dicts
    @handles(ir.Dict)
    def _(self, node: ir.Dict):
        # Flat children alternating key, value
        self.visit_children(node)
        keys = node._children[::2]
        vals = node._children[1::2]
        assert len(keys) == len(vals) # True by construction
        if len(keys) == 0:
            raise TypeError("Cannot infer type of empty dict literal")
        keyT0 = self.node_types[keys[0]]
        valT0 = self.node_types[vals[0]]
        for k in keys:
            if self.node_types[k] is not keyT0:
                raise TypeError("Heterogeneous dict keys")
        for v in vals:
            if self.node_types[v] is not valT0:
                raise TypeError("Heterogeneous dict values")
        self.node_types[node] = irT.DictT(keyT0, valT0)
        return node

    @handles(ir.DictTabulate)
    def _(self, node: ir.DictTabulate):
        self.visit_children(node)
        keys, fun = node._children
        keysT = self.node_types[keys]
        if not isinstance(keysT, irT.ListT):
            raise TypeError("DictTabulate keys must be a list")
        if not isinstance(fun, ir.Lambda):
            raise TypeError("DictTabulate expects a Lambda as second child")
        lamT = self.node_types[fun]
        if lamT.argT != keys.elemT:
            raise TypeError(f"DictTabulate lambda argument type {lamT.argT} does not match keys list element type {keysT.elemT}")
        self.node_types[node] = irT.DictT(keysT.elemT, lamT.resT)
        return node

    @handles(ir.DictGet)
    def _(self, node: ir.DictGet):
        self.visit_children(node)
        d, k = node._children
        dT = self.node_types[d]
        if not isinstance(dT, irT.DictT):
            raise TypeError("DictGet expects a dict")
        if self.node_types[k] is not dT.keyT:
            raise TypeError("DictGet key type mismatch")
        self.node_types[node] = dT.valT
        return node

    @handles(ir.DictMap)
    def _(self, node: ir.DictMap):
        self.visit_children(node)
        d, fun = node._children
        dT = self.node_types[d]
        if not isinstance(dT, irT.DictT):
            raise TypeError("DictMap expects a dict as first child")
        if not isinstance(fun, ir.Lambda):
            raise TypeError("DictMap expects a Lambda as second child")
        expected_argT = irT.TupleT(dT.keyT, dT.valT)
        lamT = self.node_types[fun]
        if lamT.argT != expected_argT:
            raise TypeError(f"DictMap lambda argument type {lamT.argT} does not match dict key/value types {expected_argT}")
        self.node_types[node] = irT.DictT(dT.keyT, lamT.resT)
        return node

    @handles(ir.DictLength)
    def _(self, node: ir.DictLength):
        self.visit_children(node)
        d = node._children[0]
        if not isinstance(self.node_types[d], irT.DictT):
            raise TypeError("DictLength expects a dict")
        self.node_types[node] = irT.Int
        return node

    # Grids
    @handles(ir.Grid)
    def _(self, node: ir.Grid):
        self.visit_children(node)
        elems = node._children
        if len(elems) == 0:
            raise TypeError("Cannot infer type of empty grid")
        elemT0 = self.node_types[elems[0]]
        for e in elems:
            if self.node_types[e] is not elemT0:
                raise TypeError("Heterogeneous grid elements")
        self.node_types[node] = irT.GridT(elemT0, "C")
        return node

    @handles(ir.GridTabulate)
    def _(self, node: ir.GridTabulate):
        self.visit_children(node)
        nR, nC, fun = node._children
        if self.node_types[nR] is not irT.Int or self.node_types[nC] is not irT.Int:
            raise TypeError("GridTabulate nR and nC must be Int")
        if not isinstance(fun, ir.Lambda):
            raise TypeError("GridTabulate expects a Lambda as third child")
        lamT = self.node_types[fun]
        if lamT.argT != irT.CellIdxT:
            raise TypeError(f"GridTabulate lambda argument type {lamT.argT} does not match CellIdxT")
        self.node_types[node] = irT.GridT(lamT.resT, "C")
        return node

    @handles(ir.GridEnumNode)
    def _(self, node: ir.GridEnumNode):
        self.visit_children(node)
        nR, nC = node._children
        if self.node_types[nR] is not irT.Int or self.node_types[nC] is not irT.Int:
            raise TypeError("GridEnumNode nR and nC must be Int")
        mode = node.mode
        if mode in ("C", "Cells"):
            elemT = irT.CellIdxT
            T = irT.ListT(elemT)
        elif mode in ("Rows", "Cols"):
            # List of lists of cell indices
            T = irT.ListT(irT.ListT(irT.CellIdxT))
        else:
            raise TypeError(f"Unknown GridEnumNode mode: {mode}")
        self.node_types[node] = T
        return node

    @handles(ir.GridWindowNode)
    def _(self, node: ir.GridWindowNode):
        self.visit_children(node)
        grid, size_r, size_c, stride_r, stride_c = node._children
        gridT = self.node_types[grid]
        if not isinstance(gridT, irT.GridT):
            raise TypeError("GridWindowNode expects a grid")
        for s in (size_r, size_c, stride_r, stride_c):
            if self.node_types[s] is not irT.Int:
                raise TypeError("GridWindowNode sizes/strides must be Int")
        # Windows enumerate grids of cells
        self.node_types[node] = irT.ListT(irT.GridT(gridT.valueT, "C"))
        return node

    @handles(ir.GridFlatNode)
    def _(self, node: ir.GridFlatNode):
        self.visit_children(node)
        grid, = node._children
        gridT = self.node_types[grid]
        if not isinstance(gridT, irT.GridT):
            raise TypeError("GridFlatNode expects a grid")
        self.node_types[node] = irT.ListT(gridT.valueT)

    @handles(ir.GridNumRows)
    def _(self, node: ir.GridNumRows):
        self.visit_children(node)
        grid = node._children[0]
        if not isinstance(self.node_types[grid], irT.GridT):
            raise TypeError("GridNumRows expects a grid")
        self.node_types[node] = irT.Int
        return node

    @handles(ir.GridNumCols)
    def _(self, node: ir.GridNumCols):
        self.visit_children(node)
        grid = node._children[0]
        if not isinstance(self.node_types[grid], irT.GridT):
            raise TypeError("GridNumCols expects a grid")
        self.node_types[node] = irT.Int
        return node

    # Higher-order / aggregations
    @handles(ir.Sum)
    def _(self, node: ir.Sum):
        self.visit_children(node)
        vals = node._children[0]
        valsT = self.node_types[vals]
        if not isinstance(valsT, irT.ListT) or (valsT.elemT is not irT.Int and valsT.elemT is not irT.Bool):
            raise TypeError("Sum expects a list of Int or Bool")
        self.node_types[node] = irT.Int
        return node

    @handles(ir.Distinct)
    def _(self, node: ir.Distinct):
        self.visit_children(node)
        vals = node._children[0]
        if not isinstance(self.node_types[vals], irT.ListT):
            raise TypeError("Distinct expects a list")
        self.node_types[node] = irT.Bool
        return node

    @handles(ir.Forall)
    def _(self, node: ir.Forall):
        self.visit_children(node)
        domain, fun = node._children
        domT = self.node_types[domain]
        if isinstance(domT, irT.ListT):
            expected_argT = domT.elemT
        elif isinstance(domT, irT.DictT):
            expected_argT = irT.TupleT(domT.keyT, domT.valT)
        else:
            raise TypeError("Forall domain must be a list or dict")
        if not isinstance(fun, ir.Lambda):
            raise TypeError("Forall expects a Lambda as second child")
        lamT = self.node_types[fun]
        if lamT.resT is not irT.Bool:
            raise TypeError("Forall lambda must return Bool")
        if lamT.argT != domT.elemT:
            raise TypeError(f"Forall lambda argument type {lamT.argT} does not match domain element type {domT.elemT}")
        self.node_types[node] = irT.Bool
        return node

    @handles(ir.Map)
    def _(self, node: ir.Map):
        self.visit_children(node)
        domain, fun = node._children
        domT = self.node_types[domain]
        if not isinstance(domT, irT.ListT):
            raise TypeError("Map expects a list as domain")
        if not isinstance(fun, ir.Lambda):
            raise TypeError("Map expects a Lambda as second child")
        lamT = self.node_types[fun]
        if lamT.argT != domT.elemT:
            raise TypeError(f"Map lambda argument type {lamT.argT} does not match domain element type {domT.elemT}")
        self.node_types[node] = irT.ListT(lamT.resT)
        return node