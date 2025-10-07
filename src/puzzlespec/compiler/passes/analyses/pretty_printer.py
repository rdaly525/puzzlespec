from __future__ import annotations

import typing as tp


from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir, ir_types as irT
from .type_inference import TypeValues
from .sym_table import SymTableEnv_
from .scope_analysis import ScopeTree

if tp.TYPE_CHECKING:
    from puzzlespec.compiler.dsl.spec import SymTable

class PrettyPrintedExpr(AnalysisObject):
    def __init__(self, text: str):
        self.text = text


class PrettyPrinterPass(Analysis):
    """Produce a human-readable string representation of expressions using infix notation.
    
    Converts expressions like Eq(Mod(Param(), Lit()), Lit()) into readable form like "nR % 2 == 0".
    Uses mathematical notation with explicit parentheses and supports:
    - Infix operators for arithmetic and comparisons
    - Parameter names from Param nodes
    - Variable indexing for array access
    - Mathematical symbols for quantifiers (∀, ∃, Σ)
    - Compact single-line set builder notation for Map operations
    - Smart bound variable names (X0, X1 for collections; x0, x1 for simple types, reused in sibling scopes)
    - Grid enumeration modes as simple names (C, Rows, Cols, etc.)
    - Multi-line formatting for quantifiers (context on first line, body indented)
    - Multi-line formatting for Conj/Disj using ∩/∪ symbols with line breaks
    
    The result is stored in the context as a `PrettyPrintedExpr` object.
    """

    requires = (TypeValues, SymTableEnv_)
    produces = (PrettyPrintedExpr,)
    name = "pretty_printer"

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        # Get analysis results
        self._types: tp.Dict[ir.Node, irT.Type_] = ctx.get(TypeValues).mapping
        self.sym: 'SymTable' = ctx.get(SymTableEnv_).sym
        self.b_names = []
        self.b_num_col = 0
        self.b_num_elem = 0

        pretty_text = self.visit(root)
        return PrettyPrintedExpr(pretty_text)
       # Literals and basic nodes
    
    @handles()
    def _(self, node: ir.Lit) -> str:
        return str(node.value)

    @handles()
    def _(self, node: ir._Param) -> str:
        return node.name

    @handles()
    def _(self, node: ir.VarRef) -> str:
        return self.sym.get_name(node.sid)

    @handles()
    def _(self, node: ir.BoundVar) -> str:
        return self.b_names[-(node.idx+1)]
    
    @handles()
    def _(self, node: ir.Lambda) -> str:
        is_col = isinstance(node.paramT, (irT.ListT, irT.DictT, irT.GridT))
        if is_col:
            bv_name = f"X{self.b_num_col}"
            self.b_num_col += 1
        else:
            bv_name = f"x{self.b_num_col}"
            self.b_num_elem += 1
        self.b_names.append(bv_name)
        body_txt = self.visit(node._children[0])
        # pop the stack
        self.b_names.pop()
        if is_col:
            self.b_num_col -= 1
        else:
            self.b_num_elem -= 1
        return bv_name, body_txt
        #return f"λ {var_name}:\n    {body_str}"


    # Arithmetic operators (binary)
    @handles()
    def _(self, node: ir.Add) -> str:
        left, right = node._children
        return f"({self.visit(left)} + {self.visit(right)})"

    @handles()
    def _(self, node: ir.Sub) -> str:
        left, right = node._children
        return f"({self.visit(left)} - {self.visit(right)})"

    @handles()
    def _(self, node: ir.Mul) -> str:
        left, right = node._children
        return f"({self.visit(left)} * {self.visit(right)})"

    @handles()
    def _(self, node: ir.Div) -> str:
        left, right = node._children
        return f"({self.visit(left)} // {self.visit(right)})"

    @handles()
    def _(self, node: ir.Mod) -> str:
        left, right = node._children
        return f"({self.visit(left)} % {self.visit(right)})"

    # Comparison operators
    @handles()
    def _(self, node: ir.Eq) -> str:
        left, right = node._children
        return f"({self.visit(left)} == {self.visit(right)})"

    @handles()
    def _(self, node: ir.Lt) -> str:
        left, right = node._children
        return f"({self.visit(left)} < {self.visit(right)})"

    @handles()
    def _(self, node: ir.LtEq) -> str:
        left, right = node._children
        return f"({self.visit(left)} <= {self.visit(right)})"

    @handles()
    def _(self, node: ir.Gt) -> str:
        left, right = node._children
        return f"({self.visit(left)} > {self.visit(right)})"

    @handles()
    def _(self, node: ir.GtEq) -> str:
        left, right = node._children
        return f"({self.visit(left)} >= {self.visit(right)})"

    # Logical operators
    @handles()
    def _(self, node: ir.And) -> str:
        left, right = node._children
        return f"({self.visit(left)} ∧ {self.visit(right)})"

    @handles()
    def _(self, node: ir.Or) -> str:
        left, right = node._children
        return f"({self.visit(left)} ∨ {self.visit(right)})"

    @handles()
    def _(self, node: ir.Not) -> str:
        child = node._children[0]
        return f"¬{self.visit(child)}"

    @handles()
    def _(self, node: ir.Implies) -> str:
        left, right = node._children
        return f"({self.visit(left)} → {self.visit(right)})"

    # Variadic logical operators
    @handles()
    def _(self, node: ir.Conj) -> str:
        if not node._children:
            return "T"
        if len(node._children) == 1:
            return self.visit(node._children[0])
        
        children_strs = [self.visit(child) for child in node._children]
        
        # Multi-line format with ∩ symbol, properly indent multi-line children
        indented_children = []
        for child_str in children_strs:
            if '\n' in child_str:
                # Child is multi-line, indent each line
                lines = child_str.split('\n')
                indented_lines = [f"    {line}" for line in lines]
                indented_children.append('\n'.join(indented_lines))
            else:
                # Child is single-line, just indent it
                indented_children.append(f"    {child_str}")
        return f"∩\n" + "\n".join(indented_children)

    @handles()
    def _(self, node: ir.Disj) -> str:
        if not node._children:
            return "F"
        if len(node._children) == 1:
            return self.visit(node._children[0])
        
        children_strs = [self.visit(child) for child in node._children]
        
        # Multi-line format with ∪ symbol, properly indent multi-line children
        indented_children = []
        for child_str in children_strs:
            if '\n' in child_str:
                # Child is multi-line, indent each line
                lines = child_str.split('\n')
                indented_lines = [f"    {line}" for line in lines]
                indented_children.append('\n'.join(indented_lines))
            else:
                # Child is single-line, just indent it
                indented_children.append(f"    {child_str}")
        return f"∪\n" + "\n".join(indented_children)

    # Collection operations
    @handles()
    def _(self, node: ir.ListGet) -> str:
        list_expr, idx_expr = node._children
        return f"{self.visit(list_expr)}[{self.visit(idx_expr)}]"

    @handles()
    def _(self, node: ir.DictGet) -> str:
        dict_expr, key_expr = node._children
        return f"{self.visit(dict_expr)}[{self.visit(key_expr)}]"

    @handles()
    def _(self, node: ir.ListLength) -> str:
        list_expr = node._children[0]
        return f"|{self.visit(list_expr)}|"

    @handles()
    def _(self, node: ir.DictLength) -> str:
        dict_expr = node._children[0]
        return f"|{self.visit(dict_expr)}|"

    # Aggregates and quantifiers
    @handles()
    def _(self, node: ir.Sum) -> str:
        vals_expr = node._children[0]
        return f"Σ({self.visit(vals_expr)})"

    @handles()
    def _(self, node: ir.Forall) -> str:
        domain_expr, fun_expr = node._children
        # Function expression should always be a Lambda by construction
        assert isinstance(fun_expr, ir.Lambda), f"Forall function expression should be Lambda, got {type(fun_expr)}"
        var_name, body_str = self.visit(fun_expr)
        # Multi-line format: context on first line, body indented on next line
        return f"∀ {var_name} ∈ {self.visit(domain_expr)}:\n    {body_str}"

    @handles()
    def _(self, node: ir.Map) -> str:
        domain_expr, fun_expr = node._children
        
        # Function expression should always be a Lambda by construction
        assert isinstance(fun_expr, ir.Lambda), f"Map function expression should be Lambda, got {type(fun_expr)}"
        var_name, body_str = self.visit(fun_expr)
        # Keep set builder notation on one line
        return f"{{{body_str} | {var_name} ∈ {self.visit(domain_expr)}}}"

    # Collections
    @handles()
    def _(self, node: ir.List) -> str:
        # Skip the first child which is the length
        elements = [self.visit(child) for child in node._children[1:]]
        return f"[{', '.join(elements)}]"

    @handles()
    def _(self, node: ir.Tuple) -> str:
        elements = [self.visit(child) for child in node._children]
        return f"({', '.join(elements)})"

    @handles()
    def _(self, node: ir.Dict) -> str:
        # Dict stores flat key-value pairs
        pairs = []
        for i in range(0, len(node._children), 2):
            key = self.visit(node._children[i])
            value = self.visit(node._children[i + 1])
            pairs.append(f"{key}: {value}")
        return f"{{{', '.join(pairs)}}}"

    # Grid operations
    @handles()
    def _(self, node: ir.GridNumRows) -> str:
        grid_expr = node._children[0]
        return f"nRows({self.visit(grid_expr)})"

    @handles()
    def _(self, node: ir.GridNumCols) -> str:
        grid_expr = node._children[0]
        return f"nCols({self.visit(grid_expr)})"


    # Additional collection operations
    @handles()
    def _(self, node: ir.ListTabulate) -> str:
        size_expr, fun_expr = node._children
        return f"tabulate({self.visit(size_expr)}, {self.visit(fun_expr)})"

    @handles()
    def _(self, node: ir.DictTabulate) -> str:
        keys_expr, fun_expr = node._children
        return f"tabulate({self.visit(keys_expr)}, {self.visit(fun_expr)})"

    @handles()
    def _(self, node: ir.ListWindow) -> str:
        list_expr, size_expr, stride_expr = node._children
        return f"windows({self.visit(list_expr)}, {self.visit(size_expr)}, {self.visit(stride_expr)})"

    @handles()
    def _(self, node: ir.ListConcat) -> str:
        left, right = node._children
        return f"({self.visit(left)} ++ {self.visit(right)})"

    @handles()
    def _(self, node: ir.ListContains) -> str:
        list_expr, elem_expr = node._children
        return f"({self.visit(elem_expr)} ∈ {self.visit(list_expr)})"

    @handles()
    def _(self, node: ir.Distinct) -> str:
        vals_expr = node._children[0]
        return f"distinct({self.visit(vals_expr)})"

    # Grid enumeration and operations
    @handles()
    def _(self, node: ir.GridEnumNode) -> str:
        nR_expr, nC_expr = node._children
        return node.mode

    @handles()
    def _(self, node: ir.GridWindowNode) -> str:
        grid_expr, size_r, size_c, stride_r, stride_c = node._children
        return f"grid_windows({self.visit(grid_expr)}, ({self.visit(size_r)}, {self.visit(size_c)}), ({self.visit(stride_r)}, {self.visit(stride_c)}))"

    @handles()
    def _(self, node: ir.GridCellAt) -> str:
        row_cells, col_cells = node._children
        return f"cell_at({self.visit(row_cells)}, {self.visit(col_cells)})"

    @handles()
    def _(self, node: ir.Grid) -> str:
        # Grid stores elements followed by nR, nC in _fields
        elements = [self.visit(child) for child in node._children]
        return f"Grid({node.nR}×{node.nC}, [{', '.join(elements)}])"

    @handles()
    def _(self, node: ir.GridTabulate) -> str:
        nR_expr, nC_expr, fun_expr = node._children
        return f"grid_tabulate({self.visit(nR_expr)}, {self.visit(nC_expr)}, {self.visit(fun_expr)})"

    @handles()
    def _(self, node: ir.OnlyElement) -> str:
        list_expr = node._children[0]
        return f"only({self.visit(list_expr)})"
