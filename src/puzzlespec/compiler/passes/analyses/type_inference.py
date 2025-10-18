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
        self.tenv: tp.Dict[int, irT.Type_] = ctx.get(TypeEnv_).env
        self.bctx = []
        # Walk and populate
        root_T = self.visit(root)
        tv = TypeValues(self._cache)
        return tv

    def visit(self, node):
        raise ValueError(f"Should never occur! {node}")
        # All visitors have been defined

    # Literals and basic nodes
    @handles(ir.Lit)
    def _(self, node: ir.Lit):
        return node.T

    @handles(ir._Param)
    def _(self, node: ir._Param):
        return node.T

    @handles(ir.VarRef)
    def _(self, var: ir.VarRef):
        assert var.sid in self.tenv
        return self.tenv[var.sid]

    @handles(ir.BoundVar)
    def visit_bound_var(self, var: ir.BoundVar):
        assert var.idx < len(self.bctx)
        return self.bctx[-(var.idx+1)]

    # Arithmetic + Boolean
    @handles(ir.Eq)
    def visit_equality(self, op: ir.Node):
        T0, T1 = self.visit_children(op)
        # Check children are same type
        if T0 != T1:
            raise TypeError(f"{op} has children of inconsistent types\n  {T0}!={T1}")
        return irT.Bool

    @handles(ir.And)
    @handles(ir.Implies)
    @handles(ir.Or)
    @handles(ir.Not)
    def visit_bool_op(self, op: ir.Node):
        cTs = self.visit_children(op)
        # Check children are bool
        for c, T in zip(op._children, cTs):
            if T != irT.Bool:
                raise TypeError(f"Child {c} of {op} is not bool")
        return irT.Bool

    @handles(ir.Neg)
    def _(self, node: ir.Neg):
        childT, = self.visit_children(node)
        if childT != irT.Int:
            raise TypeError(f"Neg expects Int, got {childT}")
        return irT.Int

    @handles(ir.Add)
    @handles(ir.Sub)
    @handles(ir.Mul)
    @handles(ir.Div)
    @handles(ir.Mod)
    def visit_int_to_int(self, op: ir.Node):
        cTs = self.visit_children(op)
        # Check children are int
        for c, T in zip(op._children, cTs):
            if T != irT.Int:
                raise TypeError(f"Child {c} of {op} is not Int")
        return irT.Int

    @handles(ir.Gt)
    @handles(ir.GtEq)
    @handles(ir.Lt)
    @handles(ir.LtEq)
    def visit_int_to_bool(self, op: ir.Node):
        cTs = self.visit_children(op)
        # Check children are int
        for c, T in zip(op._children, cTs):
            if T != irT.Int:
                raise TypeError(f"Child {c} of {op} is not Int")
        return irT.Bool

    # Variadic
    @handles(ir.Conj)
    @handles(ir.Disj)
    def visit_variadic_bool_op(self, op: ir.Node):
        cTs = self.visit_children(op)
        # Check children are bool
        for c, T in zip(op._children, cTs):
            if T != irT.Bool:
                raise TypeError(f"Child {c} of {op} is not bool")
        return irT.Bool

    @handles(ir.Sum)
    @handles(ir.Prod)
    def visit_variadic_int_op(self, op: ir.Node):
        cTs = self.visit_children(op)
        # Check children are int
        for c, T in zip(op._children, cTs):
            if T != irT.Int:
                raise TypeError(f"Child {c} of {op} is not Int")
        return irT.Int

    # Collections - Tuple nodes
    @handles(ir.Tuple)
    def visit_tuple(self, op: ir.Tuple):
        cTs = self.visit_children(op)
        return irT.TupleT(*(cT for cT in cTs))

    @handles(ir.TupleGet)
    def _(self, node: ir.TupleGet):
        tupT, = self.visit_children(node)
        if not isinstance(tupT, irT.TupleT):
            raise TypeError("TupleGet expects a tuple")
        if node.idx >= len(tupT.elementTs):
            raise TypeError(f"TupleGet index {node.idx} out of bounds for tuple of length {len(tupT.elementTs)}")
        return tupT.elementTs[node.idx]

    # Collections - List nodes
    @handles(ir.List)
    def _(self, node: ir.List):
        # children: (length, elem0, elem1, ...)
        cTs = self.visit_children(node)
        if len(cTs) == 0:
            raise TypeError("Cannot infer element type of empty list literal")
        elemT0 = cTs[0]
        for T in cTs[1:]:
            if T != elemT0:
                raise TypeError("Heterogeneous list literal elements")
        return irT.ListT(elemT0)

    @handles(ir.ListTabulate)
    def _(self, node: ir.ListTabulate):
        # size: Int, fun: Int -> V
        sizeT, lamT = self.visit_children(node)
        if sizeT is not irT.Int:
            raise TypeError("ListTabulate size must be Int")
        if lamT.argT is not irT.Int:
            raise TypeError("ListTabulate lambda key must be Int")
        return irT.ListT(lamT.resT)

    @handles(ir.ListGet)
    def _(self, node: ir.ListGet):
        lstT, idxT = self.visit_children(node)
        if not isinstance(lstT, irT.ListT):
            raise TypeError("ListGet expects a list as first operand")
        if idxT is not irT.Int:
            raise TypeError("ListGet index must be Int")
        return lstT.elemT

    @handles(ir.ListLength)
    def _(self, node: ir.ListLength):
        lstT = self.visit_children(node)
        if not isinstance(lstT, irT.ListT):
            raise TypeError("ListLength expects a list")
        return irT.Int

    @handles(ir.ListWindow)
    def _(self, node: ir.ListWindow):
        lstT, sizeT, strideT = self.visit_children(node)
        if not isinstance(lstT, irT.ListT):
            raise TypeError("ListWindow expects a list")
        if sizeT is not irT.Int or strideT is not irT.Int:
            raise TypeError("ListWindow size and stride must be Int")
        return irT.ListT(irT.ListT(lstT.elemT))

    @handles(ir.ListConcat)
    def _(self, node: ir.ListConcat):
        aT, bT = self.visit_children(node)
        if not isinstance(aT, irT.ListT) or not isinstance(bT, irT.ListT):
            raise TypeError("ListConcat expects list operands")
        if aT.elemT != bT.elemT:
            raise TypeError("ListConcat element types must match")
        return aT

    @handles(ir.ListContains)
    def _(self, node: ir.ListContains):
        listT, elemT = self.visit_children(node)
        if not isinstance(listT, irT.ListT):
            raise TypeError("ListContains expects a list as first operand")
        if elemT != listT.elemT:
            raise TypeError("ListContains element type must match list element type")
        return irT.Bool

    @handles(ir.OnlyElement)
    def _(self, node: ir.OnlyElement):
        listT, = self.visit_children(node)
        if not isinstance(listT, irT.ListT):
            raise TypeError("OnlyElement expects a list")
        return listT.elemT

    # Collections - Dict nodes
    @handles(ir.Dict)
    def _(self, node: ir.Dict):
        # Flat children alternating key, value
        Ts = self.visit_children(node)
        keyTs = Ts[::2]
        valTs= Ts[1::2]
        assert len(keyTs) == len(valTs) # True by construction
        if len(keyTs) == 0:
            raise TypeError("Cannot infer type of empty dict literal")
        keyT0 = keyTs[0]
        valT0 = valTs[0]
        for kT in keyTs[1:]:
            if kT is not keyT0:
                raise TypeError("Heterogeneous dict keys")
        for vT in valTs:
            if vT is not valT0:
                raise TypeError("Heterogeneous dict values")
        return irT.DictT(keyT0, valT0)

    @handles(ir.DictTabulate)
    def _(self, node: ir.DictTabulate):
        keysT, lamT = self.visit_children(node)
        if not isinstance(keysT, irT.ListT):
            raise TypeError("DictTabulate keys must be a list")
        if not isinstance(lamT, irT.ArrowT):
            raise TypeError("DictTabulate expects a Lambda as second child")
        if lamT.argT != keysT.elemT:
            raise TypeError(f"DictTabulate lambda argument type {lamT.argT} does not match keys list element type {keysT.elemT}")
        return irT.DictT(keysT.elemT, lamT.resT)

    @handles(ir.DictGet)
    def _(self, node: ir.DictGet):
        dT, kT = self.visit_children(node)
        if not isinstance(dT, irT.DictT):
            raise TypeError("DictGet expects a dict")
        if kT is not dT.keyT:
            raise TypeError(f"{node}: DictGet key type mismatch, expected {dT.keyT}, got {kT}")
        return dT.valT

    @handles(ir.DictMap)
    def _(self, node: ir.DictMap):
        dT, lamT = self.visit_children(node)
        if not isinstance(dT, irT.DictT):
            raise TypeError("DictMap expects a dict as first child")
        if not isinstance(lamT, irT.ArrowT):
            raise TypeError("DictMap expects a Lambda as second child")
        expected_argT = irT.TupleT(dT.keyT, dT.valT)
        if lamT.argT != expected_argT:
            raise TypeError(f"DictMap lambda argument type {lamT.argT} does not match dict key/value types {expected_argT}")
        return irT.DictT(dT.keyT, lamT.resT)

    @handles(ir.DictLength)
    def _(self, node: ir.DictLength):
        dT = self.visit_children(node)
        if not isinstance(dT, irT.DictT):
            raise TypeError("DictLength expects a dict")
        return irT.Int

    # Grid nodes
    @handles(ir.Grid)
    def _(self, node: ir.Grid):
        elemTs = self.visit_children(node)
        if len(elemTs) == 0:
            raise TypeError("Cannot infer type of empty grid")
        elemT0 = elemTs[0]
        for T in elemTs[1:]:
            if T is not elemT0:
                raise TypeError("Heterogeneous grid elements")
        return irT.GridT(elemT0, "C")

    @handles(ir.GridTabulate)
    def _(self, node: ir.GridTabulate):
        rT, cT, lamT = self.visit_children(node)
        if rT is not irT.Int or cT is not irT.Int:
            raise TypeError("GridTabulate nR and nC must be Int")
        if not isinstance(lamT, irT.ArrowT):
            raise TypeError("GridTabulate expects a Lambda as third child")
        if lamT.argT != irT.CellIdxT:
            raise TypeError(f"GridTabulate lambda argument type {lamT.argT} does not match CellIdxT")
        # TODO, something off about the 'mode'
        return irT.GridT(lamT.resT, "C")

    @handles(ir.GridEnumNode)
    def _(self, node: ir.GridEnumNode):
        rT, cT = self.visit_children(node)
        if rT is not irT.Int or cT is not irT.Int:
            raise TypeError("GridEnumNode nR and nC must be Int")
        mode = node.mode
        if mode in ("Cells",):
            elemT = irT.CellIdxT
            T = irT.ListT(elemT)
        elif mode in ("Rows", "Cols"):
            # List of lists of cell indices
            T = irT.ListT(irT.ListT(irT.CellIdxT))
        elif mode in ("CellGrid",):
            T = irT.GridT(irT.CellIdxT, "C")
        else:
            raise TypeError(f"Unknown GridEnumNode mode: {mode}")
        return T

    @handles(ir.GridFlatNode)
    def _(self, node: ir.GridFlatNode):
        gridT, = self.visit_children(node)
        if not isinstance(gridT, irT.GridT):
            raise TypeError("GridFlatNode expects a grid")
        return irT.ListT(gridT.valueT)

    @handles(ir.GridWindowNode)
    def _(self, node: ir.GridWindowNode):
        gridT, size_rT, size_cT, stride_rT, stride_cT = self.visit_children(node)
        if not isinstance(gridT, irT.GridT):
            raise TypeError("GridWindowNode expects a grid")
        for s in (size_rT, size_cT, stride_rT, stride_cT):
            if s is not irT.Int:
                raise TypeError("GridWindowNode sizes/strides must be Int")
        # Windows enumerate grids of cells
        return irT.ListT(irT.GridT(gridT.valueT, "C"))

    @handles(ir.GridDims)
    def _(self, node: ir.GridDims):
        dimT = self.visit_children(node)
        if dimT is not irT.TupleT(irT.Int, irT.Int):
            raise TypeError("GridDims expects a tuple of Ints")
        return dimT

    # Higher Order Operators
    @handles(ir.Lambda)
    def _(self, lam: ir.Lambda):
        self.bctx.append(lam.paramT)
        resT, = self.visit_children(lam)
        self.bctx.pop()
        argT = lam.paramT
        return irT.ArrowT(argT, resT)

    @handles(ir.Map)
    def _(self, node: ir.Map):
        domainT, funT = self.visit_children(node)
        if not isinstance(domainT, irT.ListT):
            raise TypeError(f"Map expects a list as domain, got {domainT}")
        if not isinstance(funT, irT.ArrowT):
            raise TypeError(f"Map expects a Lambda as second child, got {funT}")
        if funT.argT != domainT.elemT:
            raise TypeError(f"Map lambda argument type {funT.argT} does not match domain element type {domainT.elemT}")
        return irT.ListT(funT.resT)

    @handles(ir.Fold)
    def _(self, node: ir.Fold):
        domainT, funT, initT = self.visit_children(node)
        if not isinstance(domainT, irT.ListT):
            raise TypeError("Fold expects a list as domain")
        if not isinstance(funT, irT.ArrowT):
            raise TypeError("Fold expects a Lambda as second child")
        # Should be (a -> b -> b) -> b ->List[a] -> b
        aT = domainT.elemT
        bT = funT.resT
        if initT != bT:
            raise TypeError(f"Fold init type {initT} does not match domain element type {domainT.elemT}")
        if funT != irT.ArrowT(irT.TupleT(aT, bT), bT):
            raise TypeError(f"Fold lambda must have argument type {aT} and result type {bT}")
        return bT

    @handles(ir.SumReduce)
    def _(self, node: ir.SumReduce):
        valsT, = self.visit_children(node)
        if not isinstance(valsT, irT.ListT) or valsT.elemT not in (irT.Int, irT.Bool):
            raise TypeError(f"SumReduce expects a list of Int or Bool, got {valsT}")
        return irT.Int

    @handles(ir.ProdReduce)
    def _(self, node: ir.ProdReduce):
        valsT, = self.visit_children(node)
        if not isinstance(valsT, irT.ListT) or valsT.elemT is not irT.Int:
            raise TypeError("ProdReduce expects a list of Int")
        return irT.Int

    @handles(ir.Forall)
    def _(self, node: ir.Forall):
        domainT, lamT = self.visit_children(node)
        if not isinstance(domainT, irT.ListT):
            raise TypeError("Forall domain must be a list")
        if not isinstance(lamT, irT.ArrowT):
            raise TypeError("Forall expects a Lambda as second child")
        if lamT.resT is not irT.Bool:
            raise TypeError("Forall lambda must return Bool")
        if lamT.argT != domainT.elemT:
            raise TypeError(f"Forall lambda argument type {lamT.argT} does not match domain element type {domainT.elemT}")
        return irT.Bool

    @handles(ir.Exists)
    def _(self, node: ir.Exists):
        domainT, lamT = self.visit_children(node)
        if not isinstance(domainT, irT.ListT):
            raise TypeError("Exists domain must be a list")
        if not isinstance(lamT, irT.ArrowT):
            raise TypeError("Exists expects a Lambda as second child")
        if lamT.resT is not irT.Bool:
            raise TypeError("Exists lambda must return Bool")
        if lamT.argT != domainT.elemT:
            raise TypeError(f"Exists lambda argument type {lamT.argT} does not match domain element type {domainT.elemT}")
        return irT.Bool

    @handles(ir.Distinct)
    def _(self, node: ir.Distinct):
        valsT, = self.visit_children(node)
        if not isinstance(valsT, irT.ListT):
            raise TypeError(f"{node}: Distinct expects a list, got {valsT}")
        return irT.Bool

    # Functions that should not be here - moved to bottom
    @handles(ir._LambdaPlaceholder)
    @handles(ir._BoundVarPlaceholder)
    def _(self, node: ir.Node): 
        raise ValueError(f"SHOULD NOT BE HERE {node}")