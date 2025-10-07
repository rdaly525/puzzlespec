from __future__ import annotations

import typing as tp


from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir, ir_types as irT
from .type_inference import TypeValues, TypeEnv_
from .sym_table import SymTableEnv_

if tp.TYPE_CHECKING:
    from puzzlespec.compiler.dsl.spec import SymTable

class PrettyPrintedExpr(AnalysisObject):
    def __init__(self, text: str):
        self.text = text

def subscript(n: int) -> str:
    # handle mutliple digits
    table = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    return "".join(table[d] for d in str(n))

def superscript(n: int) -> str:
    table = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
    return "".join(table[d] for d in str(n))

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

    requires = (TypeEnv_, SymTableEnv_)
    produces = (PrettyPrintedExpr,)
    name = "pretty_printer"

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        # Get analysis results
        self.tenv = ctx.get(TypeEnv_).env
        self.sym: 'SymTable' = ctx.get(SymTableEnv_).sym
        self.p_to_T = {}
        self.g_to_T = {}
        self.d_to_T = {}
        self.b_names = []
        self.b_num_col = 0
        self.b_num_elem = 0

        constraint_text = self.visit(root)
        s = "Params:\n"        
        for pname, T in self.p_to_T.items():
            s += f"    {pname}: {T}\n"
        s += "Gen vars:\n"
        for gname, T in self.g_to_T.items():
            s += f"    {gname}: {T}\n"
        s += "Decision vars:\n"
        for dname, T in self.d_to_T.items():
            s += f"    {dname}: {T}\n"
        s += constraint_text
        return PrettyPrintedExpr(s)
       # Literals and basic nodes
    
    @handles()
    def _(self, node: ir.Lit) -> str:
        return str(node.value)

    @handles()
    def _(self, node: ir._Param) -> str:
        self.p_to_T[node.name] = node.T
        return node.name

    @handles()
    def _(self, node: ir.VarRef) -> str:
        e = self.sym[node.sid]
        name, role = e.name, e.role
        T = self.tenv[node.sid]
        if role=='P':
            self.p_to_T[name] = T
        elif role=='G':
            self.g_to_T[name] = T
        elif role=='D':
            self.d_to_T[name] = T
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
        body_txt, = self.visit_children(node)
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
        ltext, rtext = self.visit_children(node)
        return f"({ltext} + {rtext})"

    @handles()
    def _(self, node: ir.Sub) -> str:
        left, right = self.visit_children(node)
        return f"({left} - {right})"

    @handles()
    def _(self, node: ir.Mul) -> str:
        left, right = self.visit_children(node)
        return f"({left} * {right})"

    @handles()
    def _(self, node: ir.Div) -> str:
        left, right = self.visit_children(node)
        return f"({left} // {right})"

    @handles()
    def _(self, node: ir.Mod) -> str:
        left, right = self.visit_children(node)
        return f"({left} % {right})"

    # Comparison operators
    @handles()
    def _(self, node: ir.Eq) -> str:
        left, right = self.visit_children(node)
        return f"({left} = {right})"

    @handles()
    def _(self, node: ir.Lt) -> str:
        left, right = self.visit_children(node)
        return f"({left} < {right})"

    @handles()
    def _(self, node: ir.LtEq) -> str:
        left, right = self.visit_children(node)
        return f"({left} ≤ {right})"

    @handles()
    def _(self, node: ir.Gt) -> str:
        left, right = self.visit_children(node)
        return f"({left} > {right})"

    @handles()
    def _(self, node: ir.GtEq) -> str:
        left, right = self.visit_children(node)
        return f"({left} ≥ {right})"

    # Logical operators
    @handles()
    def _(self, node: ir.And) -> str:
        left, right = self.visit_children(node)
        return f"({left} ∧ {right})"

    @handles()
    def _(self, node: ir.Or) -> str:
        left, right = self.visit_children(node)
        return f"({left} ∨ {right})"

    @handles()
    def _(self, node: ir.Not) -> str:
        child, = self.visit_children(node)
        return f"¬{child}"

    @handles()
    def _(self, node: ir.Implies) -> str:
        left, right = self.visit_children(node)
        return f"({left} → {right})"

    # Variadic logical operators
    @handles()
    def _(self, node: ir.Conj) -> str:
        children_strs = self.visit_children(node)
        if not children_strs:
            return "T"
        if len(children_strs) == 1:
            return children_strs[0]
        
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
        children_strs = self.visit_children(node)
        if not children_strs:
            return "F"
        if len(children_strs) == 1:
            return children_strs[0]
        
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
        list_expr, idx_expr = self.visit_children(node)
        return f"{list_expr}[{idx_expr}]"

    @handles()
    def _(self, node: ir.DictGet) -> str:
        dict_expr, key_expr = self.visit_children(node)
        return f"{dict_expr}[{key_expr}]"

    @handles()
    def _(self, node: ir.ListLength) -> str:
        list_expr, = self.visit_children(node)
        return f"|{list_expr}|"

    @handles()
    def _(self, node: ir.DictLength) -> str:
        dict_expr, = self.visit_children(node)
        return f"|{dict_expr}|"

    # Aggregates and quantifiers
    @handles()
    def _(self, node: ir.Sum) -> str:
        vals_expr, = self.visit_children(node)
        return f"Σ({vals_expr})"

    @handles()
    def _(self, node: ir.Forall) -> str:
        domain_expr, fun_expr = node._children
        assert isinstance(fun_expr, ir.Lambda), f"Forall function expression should be Lambda, got {type(fun_expr)}"
        var_name, body_str = self.visit(fun_expr)
        domain_str = self.visit(domain_expr)
        # Multi-line format: context on first line, body indented on next line
        return f"∀ {var_name} ∈ {domain_str}:\n    {body_str}"

    @handles()
    def _(self, node: ir.Map) -> str:
        domain_expr, fun_expr = node._children
        assert isinstance(fun_expr, ir.Lambda), f"Forall function expression should be Lambda, got {type(fun_expr)}"
        var_name, body_str = self.visit(fun_expr)
        domain_str = self.visit(domain_expr)
        # Keep set builder notation on one line
        return f"{{{body_str} | {var_name} ∈ {domain_str}}}"

    # Collections
    @handles()
    def _(self, node: ir.List) -> str:
        # Skip the first child which is the length
        children = self.visit_children(node)
        return f"[{', '.join(children)}]"

    @handles()
    def _(self, node: ir.Tuple) -> str:
        elements = self.visit_children(node)
        return f"({', '.join(elements)})"

    @handles()
    def _(self, node: ir.Dict) -> str:
        # Dict stores flat key-value pairs
        children = self.visit_children(node)
        pairs = []
        for i in range(0, len(children), 2):
            key = children[i]
            value = children[i + 1]
            pairs.append(f"{key}: {value}")
        return f"{{{', '.join(pairs)}}}"

    # Grid operations
    @handles()
    def _(self, node: ir.GridNumRows) -> str:
        grid_expr, = self.visit_children(node)
        return f"nRows({grid_expr})"

    @handles()
    def _(self, node: ir.GridNumCols) -> str:
        grid_expr, = self.visit_children(node)
        return f"nCols({grid_expr})"


    # Additional collection operations
    @handles()
    def _(self, node: ir.ListTabulate) -> str:
        size_expr, fun_expr = node._children
        var_name, body_str = self.visit(fun_expr)
        size_str = self.visit(size_expr)
        return f"{{{body_str} | {var_name} ∈ (1..{size_str})}}"

    @handles()
    def _(self, node: ir.DictTabulate) -> str:
        keys_expr, fun_expr = self.visit_children(node)
        return f"tabulate({keys_expr}, {fun_expr})"

    @handles()
    def _(self, node: ir.ListWindow) -> str:
        list_expr, size_expr, stride_expr = self.visit_children(node)
        return f"{list_expr}.windows({size_expr},{stride_expr})"

    @handles()
    def _(self, node: ir.ListConcat) -> str:
        left, right = self.visit_children(node)
        return f"({left} ++ {right})"

    @handles()
    def _(self, node: ir.ListContains) -> str:
        list_expr, elem_expr = self.visit_children(node)
        return f"({elem_expr} ∈ {list_expr})"

    @handles()
    def _(self, node: ir.Distinct) -> str:
        vals_expr, = self.visit_children(node)
        return f"distinct({vals_expr})"

    # Grid enumeration and operations
    @handles()
    def _(self, node: ir.GridEnumNode) -> str:
        nR_expr, nC_expr = self.visit_children(node)
        match (node.mode):
            case "Cells":
                return "[Cells]"
            case "Rows" | "Cols":
                return f"[{node.mode}]"
            case "CellGrid":
                return "[[Cells]]"
            case (_):
                raise NotImplementedError(f"{node.mode} is not support")

    @handles()
    def _(self, node: ir.GridFlatNode) -> str:
        grid_str, = self.visit_children(node)
        return f"vec({grid_str})"

    @handles()
    def _(self, node: ir.GridWindowNode) -> str:
        grid_expr, size_r, size_c, stride_r, stride_c = self.visit_children(node)
        return f"{grid_expr}.tiles({size_r}x{size_c}, {stride_r}x{stride_c})"

    @handles()
    def _(self, node: ir.Grid) -> str:
        # Grid stores elements followed by nR, nC in _fields
        elements = self.visit_children(node)
        return f"Grid({node.nR}×{node.nC}, [{', '.join(elements)}])"

    @handles()
    def _(self, node: ir.GridTabulate) -> str:
        nR_expr, nC_expr, fun_expr = node._children
        var_name, body_str = self.visit(fun_expr)
        nR, nC = self.visit(nR_expr), self.visit(nC_expr)
        return f"{{{body_str} | {var_name} ∈ ((1,1)..({nR},{nC}))}}"

    @handles()
    def _(self, node: ir.OnlyElement) -> str:
        list_expr, = self.visit_children(node)
        return f"{list_expr}.only)"
