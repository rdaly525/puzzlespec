from ..pass_base import Context, AnalysisObject, Analysis, handles
from ...dsl import ir, ast, ir_types as irT, spec
import typing as tp


class TypeEnv_(AnalysisObject):
    def __init__(self, env: spec.TypeEnv):
        self.env = env

class TypeValues(AnalysisObject):
    def __init__(self):
        self.mapping: tp.Dict[ir.Node, irT.Type_] = {}

class TypeInferencePass(Analysis):
    requires = (TypeEnv_,)
    produces = (TypeValues,)
    name = "type_inference"
    def __init__(self):
        super().__init__()

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        # Use concrete mapping for fast lookup
        self.var_types: tp.Dict[str, irT.Type_] = ctx.get(TypeEnv_).env.vars
        self.node_types: tp.Dict[ir.Node, irT.Type_] = {}
        # Walk and populate
        self.visit(root)
        # Package result
        tv = TypeValues()
        tv.mapping = self.node_types
        return tv

    def _visit_children(self, node: ir.Node) -> None:
        for child in node._children:
            self.visit(child)

    @handles(ir.FreeVar)
    def visit_free_var(self, var: ir.FreeVar):
        if var.name in self.var_types:
            self.node_types[var] = self.var_types[var.name]
        else:
            raise TypeError(f"Variable {var.name} not found in type environment")
        return var

    @handles(ir.BoundVar)
    def visit_bound_var(self, var: ir.BoundVar):
        # Bound variable types are assigned contextually when visiting enclosing lambdas
        # If encountered outside such a context, this is a type error
        if var not in self.node_types:
            raise TypeError("Encountered untyped bound variable outside of lambda context")
        return var

    @handles(ir.And, ir.Or, ir.Implies)
    def visit_bool_binary_op(self, op: ir.Node):
        self._visit_children(op)
        # Check children are bool
        for child in op._children:
            if self.node_types[child] != irT.Bool:
                raise TypeError(f"Child {child} of {op} is not bool")
        self.node_types[op] = irT.Bool
        return op

    @handles(ir.Conj)
    def _(self, op: ir.Conj):
        self._visit_children(op)
        for child in op._children:
            if self.node_types[child] is not irT.Bool:
                raise TypeError(f"Child {child} of {op} is not Bool")
        self.node_types[op] = irT.Bool
        return op

    @handles(ir.Disj)
    def _(self, op: ir.Disj):
        self._visit_children(op)
        for child in op._children:
            if self.node_types[child] is not irT.Bool:
                raise TypeError(f"Child {child} of {op} is not Bool")
        self.node_types[op] = irT.Bool
        return op

    # Visit int, int -> int ops
    @handles(ir.Add, ir.Sub, ir.Mul, ir.Div, ir.Mod)
    def visit_int_binary_op(self, op: ir.Node):
        self._visit_children(op)
        # Check children are int
        for child in op._children:
            if self.node_types[child] != irT.Int:
                raise TypeError(f"Child {child} of {op} is not int")
        self.node_types[op] = irT.Int
        return op
    
    # Visit int, int -> bool ops
    @handles(ir.Gt, ir.GtEq, ir.Lt, ir.LtEq)
    def visit_int_comparison_op(self, op: ir.Node):
        self._visit_children(op)
        # Check children are int
        for child in op._children:
            if self.node_types[child] != irT.Int:
                raise TypeError(f"Child {child} of {op} is not int")
        self.node_types[op] = irT.Bool
        return op

    # Equality
    @handles(ir.Eq)
    def visit_equality(self, op: ir.Node):
        self._visit_children(op)
        # Check children are same type
        for child in op._children:
            if self.node_types[child] != self.node_types[op._children[0]]:
                raise TypeError(f"Child {child} of {op} is not same type as {op._children[0]}")
        self.node_types[op] = irT.Bool
        return op

    # Tuples
    @handles(ir.Tuple)
    def visit_tuple(self, op: ir.Tuple):
        self._visit_children(op)
        self.node_types[op] = irT.TupleT(*(self.node_types[c] for c in op._children))
        return op
    
    # Literals and simple nodes
    @handles(ir.Lit)
    def _(self, node: ir.Lit):
        val = node.value
        if isinstance(val, bool):
            self.node_types[node] = irT.Bool
        elif isinstance(val, int):
            self.node_types[node] = irT.Int
        else:
            raise TypeError(f"Unsupported literal type: {type(val)}")
        return node

    @handles(ir.Param)
    def _(self, node: ir.Param):
        # Params are integer-typed in this DSL
        self.node_types[node] = irT.Int
        return node

    @handles(ir.Not)
    def _(self, node: ir.Not):
        for child in node._children:
            self.visit(child)
        child = node._children[0]
        if self.node_types[child] is not irT.Bool:
            raise TypeError("Not expects Bool operand")
        self.node_types[node] = irT.Bool
        return node

    # Helper: infer lambda with a given argument type
    def _infer_lambda(self, lam: ir.Lambda, argT: irT.Type_) -> irT.ArrowT:
        bound_var = lam._children[0]
        body = lam._children[1]
        if not isinstance(bound_var, ir.BoundVar):
            raise TypeError("Lambda first child must be a BoundVar")
        # Assign bound var type in this context
        self.node_types[bound_var] = argT
        # Infer body type
        self.visit(body)
        resT = self.node_types[body]
        lamT = irT.ArrowT(argT, resT)
        self.node_types[lam] = lamT
        return lamT

    # Lists
    @handles(ir.List)
    def _(self, node: ir.List):
        # children: (length, elem0, elem1, ...)
        for child in node._children:
            self.visit(child)
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
        # size: Int, fun: Lambda(Int -> T)
        size, fun = node._children
        self.visit(size)
        if self.node_types[size] is not irT.Int:
            raise TypeError("ListTabulate size must be Int")
        if not isinstance(fun, ir.Lambda):
            raise TypeError("ListTabulate expects a Lambda as second child")
        lamT = self._infer_lambda(fun, irT.Int)
        self.node_types[node] = irT.ListT(lamT.resT)
        return node

    @handles(ir.VarList)
    def _(self, node: ir.VarList):
        # size child; declared type from environment by name
        size = node._children[0]
        self.visit(size)
        if self.node_types[size] is not irT.Int:
            raise TypeError("VarList size must be Int")
        name = node.name
        if name not in self.var_types:
            raise TypeError(f"VarList {name} not found in type environment")
        T = self.var_types[name]
        if not isinstance(T, irT.ListT):
            raise TypeError(f"VarList {name} must have list type; got {T}")
        self.node_types[node] = T
        return node

    @handles(ir.ListGet)
    def _(self, node: ir.ListGet):
        lst, idx = node._children
        self.visit(lst)
        self.visit(idx)
        lstT = self.node_types[lst]
        if not isinstance(lstT, irT.ListT):
            raise TypeError("ListGet expects a list as first operand")
        if self.node_types[idx] is not irT.Int:
            raise TypeError("ListGet index must be Int")
        self.node_types[node] = lstT.elemT
        return node

    @handles(ir.ListLength)
    def _(self, node: ir.ListLength):
        lst = node._children[0]
        self.visit(lst)
        lstT = self.node_types[lst]
        if not isinstance(lstT, irT.ListT):
            raise TypeError("ListLength expects a list")
        self.node_types[node] = irT.Int
        return node

    @handles(ir.ListWindow)
    def _(self, node: ir.ListWindow):
        lst, size, stride = node._children
        for ch in node._children:
            self.visit(ch)
        if not isinstance(self.node_types[lst], irT.ListT):
            raise TypeError("ListWindow expects a list")
        if self.node_types[size] is not irT.Int or self.node_types[stride] is not irT.Int:
            raise TypeError("ListWindow size and stride must be Int")
        elemT = tp.cast(irT.ListT, self.node_types[lst]).elemT
        self.node_types[node] = irT.ListT(irT.ListT(elemT))
        return node

    @handles(ir.ListConcat)
    def _(self, node: ir.ListConcat):
        a, b = node._children
        self.visit(a)
        self.visit(b)
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
        for ch in node._children:
            self.visit(ch)
        keys = node._children[::2]
        vals = node._children[1::2]
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
        keys, fun = node._children
        self.visit(keys)
        keysT = self.node_types[keys]
        if not isinstance(keysT, irT.ListT):
            raise TypeError("DictTabulate keys must be a list")
        if not isinstance(fun, ir.Lambda):
            raise TypeError("DictTabulate expects a Lambda as second child")
        lamT = self._infer_lambda(fun, keysT.elemT)
        self.node_types[node] = irT.DictT(keysT.elemT, lamT.resT)
        return node

    @handles(ir.VarDict)
    def _(self, node: ir.VarDict):
        keys = node._children[0]
        self.visit(keys)
        name = node.name
        if name not in self.var_types:
            raise TypeError(f"VarDict {name} not found in type environment")
        T = self.var_types[name]
        if not isinstance(T, irT.DictT):
            raise TypeError(f"VarDict {name} must have dict type; got {T}")
        # Optional: check key list type consistency if available
        keysT = self.node_types[keys]
        if isinstance(keysT, irT.ListT) and keysT.elemT is not T.keyT:
            raise TypeError("VarDict keys element type does not match declared key type")
        self.node_types[node] = T
        return node

    @handles(ir.DictGet)
    def _(self, node: ir.DictGet):
        d, k = node._children
        self.visit(d)
        self.visit(k)
        dT = self.node_types[d]
        if not isinstance(dT, irT.DictT):
            raise TypeError("DictGet expects a dict")
        if self.node_types[k] is not dT.keyT:
            raise TypeError("DictGet key type mismatch")
        self.node_types[node] = dT.valT
        return node

    @handles(ir.DictMap)
    def _(self, node: ir.DictMap):
        d, fun = node._children
        self.visit(d)
        dT = self.node_types[d]
        if not isinstance(dT, irT.DictT):
            raise TypeError("DictMap expects a dict as first child")
        if not isinstance(fun, ir.Lambda):
            raise TypeError("DictMap expects a Lambda as second child")
        argT = irT.TupleT(dT.keyT, dT.valT)
        lamT = self._infer_lambda(fun, argT)
        self.node_types[node] = irT.DictT(dT.keyT, lamT.resT)
        return node

    @handles(ir.DictLength)
    def _(self, node: ir.DictLength):
        d = node._children[0]
        self.visit(d)
        if not isinstance(self.node_types[d], irT.DictT):
            raise TypeError("DictLength expects a dict")
        self.node_types[node] = irT.Int
        return node

    # Grids
    @handles(ir.Grid)
    def _(self, node: ir.Grid):
        # Concrete grid: infer element type from children if present
        for ch in node._children:
            self.visit(ch)
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
        nR, nC, fun = node._children
        self.visit(nR)
        self.visit(nC)
        if self.node_types[nR] is not irT.Int or self.node_types[nC] is not irT.Int:
            raise TypeError("GridTabulate nR and nC must be Int")
        if not isinstance(fun, ir.Lambda):
            raise TypeError("GridTabulate expects a Lambda as third child")
        lamT = self._infer_lambda(fun, irT.CellIdxT)
        self.node_types[node] = irT.GridT(lamT.resT, "C")
        return node

    @handles(ir.GridEnumNode)
    def _(self, node: ir.GridEnumNode):
        nR, nC = node._children
        self.visit(nR)
        self.visit(nC)
        if self.node_types[nR] is not irT.Int or self.node_types[nC] is not irT.Int:
            raise TypeError("GridEnumNode nR and nC must be Int")
        mode = node.mode
        if mode in ("C", "Cells"):
            elemT = irT.CellIdxT
            T = irT.ListT(elemT)
        elif mode in ("V", "Verts"):
            elemT = irT.VertexIdxT
            T = irT.ListT(elemT)
        elif mode in ("EH", "EV", "Edges"):
            elemT = irT.EdgeIdxT
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
        grid, size_r, size_c, stride_r, stride_c = node._children
        for ch in node._children:
            self.visit(ch)
        gridT = self.node_types[grid]
        if not isinstance(gridT, irT.GridT):
            raise TypeError("GridWindowNode expects a grid")
        for s in (size_r, size_c, stride_r, stride_c):
            if self.node_types[s] is not irT.Int:
                raise TypeError("GridWindowNode sizes/strides must be Int")
        # Windows enumerate grids of cells
        self.node_types[node] = irT.ListT(irT.GridT(gridT.valueT, "C"))
        return node

    @handles(ir.GridNumRows)
    def _(self, node: ir.GridNumRows):
        grid = node._children[0]
        self.visit(grid)
        if not isinstance(self.node_types[grid], irT.GridT):
            raise TypeError("GridNumRows expects a grid")
        self.node_types[node] = irT.Int
        return node

    @handles(ir.GridNumCols)
    def _(self, node: ir.GridNumCols):
        grid = node._children[0]
        self.visit(grid)
        if not isinstance(self.node_types[grid], irT.GridT):
            raise TypeError("GridNumCols expects a grid")
        self.node_types[node] = irT.Int
        return node

    # Higher-order / aggregations
    @handles(ir.Sum)
    def _(self, node: ir.Sum):
        vals = node._children[0]
        self.visit(vals)
        valsT = self.node_types[vals]
        if not isinstance(valsT, irT.ListT) or (valsT.elemT is not irT.Int and valsT.elemT is not irT.Bool):
            raise TypeError("Sum expects a list of Int or Bool")
        self.node_types[node] = irT.Int
        return node

    @handles(ir.Distinct)
    def _(self, node: ir.Distinct):
        vals = node._children[0]
        self.visit(vals)
        if not isinstance(self.node_types[vals], irT.ListT):
            raise TypeError("Distinct expects a list")
        self.node_types[node] = irT.Bool
        return node

    @handles(ir.Forall)
    def _(self, node: ir.Forall):
        domain, fun = node._children
        self.visit(domain)
        domT = self.node_types[domain]
        if isinstance(domT, irT.ListT):
            expected_argT = domT.elemT
        elif isinstance(domT, irT.DictT):
            expected_argT = irT.TupleT(domT.keyT, domT.valT)
        else:
            raise TypeError("Forall domain must be a list or dict")
        if not isinstance(fun, ir.Lambda):
            raise TypeError("Forall expects a Lambda as second child")
        lamT = self._infer_lambda(fun, expected_argT)
        if lamT.resT is not irT.Bool:
            raise TypeError("Forall lambda must return Bool")
        self.node_types[node] = irT.Bool
        return node

    @handles(ir.Map)
    def _(self, node: ir.Map):
        domain, fun = node._children
        self.visit(domain)
        domT = self.node_types[domain]
        if not isinstance(domT, irT.ListT):
            raise TypeError("Map expects a list as domain")
        if not isinstance(fun, ir.Lambda):
            raise TypeError("Map expects a Lambda as second child")
        lamT = self._infer_lambda(fun, domT.elemT)
        self.node_types[node] = irT.ListT(lamT.resT)
        return node

    #@handles(ir.Mask)
    #def _(self, node: ir.Mask):
    #    mask, vals = node._children
    #    self.visit(mask)
    #    self.visit(vals)
    #    maskT = self.node_types[mask]
    #    # Only dict-mask is well-defined in available types; returns key type
    #    if isinstance(maskT, irT.DictT):
    #        if maskT.valT is not irT.Bool:
    #            raise TypeError("Dict mask values must be Bool")
    #        self.node_types[node] = maskT.keyT
    #        return node
    #    raise TypeError("Unsupported mask operand types for current type system")