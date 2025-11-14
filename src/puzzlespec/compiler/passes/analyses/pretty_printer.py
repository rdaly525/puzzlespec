from __future__ import annotations

import typing as tp


from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir, ir_types as irT
from .sym_table import SymTableEnv_
from ..envobj import EnvsObj

if tp.TYPE_CHECKING:
    from puzzlespec.compiler.dsl.spec import SymTable

class PrettyPrintedExpr(AnalysisObject):
    def __init__(self, text: str):
        self.text = text

#def subscript(n: int) -> str:
#    # handle mutliple digits
#    table = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
#    return "".join(table[d] for d in str(n))
#
#def superscript(n: int) -> str:
#    table = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
#    return "".join(table[d] for d in str(n))

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

    requires = (EnvsObj,)
    produces = (PrettyPrintedExpr,)
    name = "pretty_printer"

    def visit(self, node):
        raise NotImplementedError("Should never be here!")
        # All node kinds have a custom visit

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        # Get analysis results
        self.tenv = ctx.get(EnvsObj).tenv
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

    @handles()
    def _(self, node: ir.Unit) -> str:
        return "tt"

    # Literals and basic nodes
    @handles()
    def _(self, node: ir.Lit) -> str:
        if node.T is irT.Bool:
            return '𝕋' if node.val else '𝔽'
        return str(node.val)

    # Note: _Param node no longer exists in ir.py

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
    
    @handles(mark_invalid=True)
    def _(self, node: ir._BoundVarPlaceholder) -> str:
        ...

    # Arithmetic + Boolean
    @handles()
    def _(self, node: ir.Eq) -> str:
        left, right = self.visit_children(node)
        return f"({left} = {right})"

    @handles()
    def _(self, node: ir.And) -> str:
        left, right = self.visit_children(node)
        return f"({left} ∧ {right})"

    @handles()
    def _(self, node: ir.Implies) -> str:
        left, right = self.visit_children(node)
        return f"({left} → {right})"

    @handles()
    def _(self, node: ir.Or) -> str:
        left, right = self.visit_children(node)
        return f"({left} ∨ {right})"

    @handles()
    def _(self, node: ir.Not) -> str:
        child, = self.visit_children(node)
        return f"¬{child}"

    @handles()
    def _(self, node: ir.Neg) -> str:
        child, = self.visit_children(node)
        return f"(-{child})"

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

    @handles()
    def _(self, node: ir.Gt) -> str:
        left, right = self.visit_children(node)
        return f"({left} > {right})"

    @handles()
    def _(self, node: ir.GtEq) -> str:
        left, right = self.visit_children(node)
        return f"({left} ≥ {right})"

    @handles()
    def _(self, node: ir.Lt) -> str:
        left, right = self.visit_children(node)
        return f"({left} < {right})"

    @handles()
    def _(self, node: ir.LtEq) -> str:
        left, right = self.visit_children(node)
        return f"({left} ≤ {right})"

    @handles()
    def _(self, node: ir.Ite) -> str:
        pred, t, f = self.visit_children(node)
        return f"if {pred} then {t} else {f}"

    # Variadic
    @handles()
    def _(self, node: ir.Conj) -> str:
        children_strs = self.visit_children(node)
        if not children_strs:
            return '𝕋'
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
            return '𝔽'
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

    @handles()
    def _(self, node: ir.Sum) -> str:
        children_strs = self.visit_children(node)
        return f"Σ({children_strs})"

    @handles()
    def _(self, node: ir.Prod) -> str:
        # TODO: Implement Prod pretty printing
        children_strs = self.visit_children(node)
        return f"Π({children_strs})"
    
    ## Domains
    @handles()
    def _(self, node: ir.Universe) -> str:
        # TODO: Determine how to pretty print Universe domain
        return f"Universe({node.T})"

    @handles()
    def _(self, node: ir.Fin) -> str:
        n_expr, = self.visit_children(node)
        return f"Fin({n_expr})"

    @handles()
    def _(self, node: ir.Enum) -> str:
        # TODO: Determine how to pretty print Enum domain
        return f"Enum({node.enumT.name})"

    @handles()
    def _(self, node: ir.EnumLit) -> str:
        return node.label

    @handles()
    def _(self, node: ir.Card) -> str:
        domain_expr, = self.visit_children(node)
        return f"|{domain_expr}|"

    @handles()
    def _(self, node: ir.IsMember) -> str:
        domain_expr, val_expr = self.visit_children(node)
        return f"({val_expr} ∈ {domain_expr})"

    ## Cartesian Products
    @handles()
    def _(self, node: ir.CartProd) -> str:
        # TODO: Determine how to pretty print CartProd domain
        doms = self.visit_children(node)
        return f"×({', '.join(doms)})"

    @handles()
    def _(self, node: ir.DomProj) -> str:
        # TODO: Determine how to pretty print DomProj
        dom_expr, = self.visit_children(node)
        return f"{dom_expr}.{node.idx}"

    # Collections - Tuple nodes
    @handles()
    def _(self, node: ir.TupleLit) -> str:
        elements = self.visit_children(node)
        return f"({', '.join(elements)})"

    @handles()
    def _(self, node: ir.Proj) -> str:
        tup_expr, = self.visit_children(node)
        return f"{tup_expr}.{node.idx}"

    @handles()
    def _(self, node: ir.DisjUnion) -> str:
        # TODO: Determine how to pretty print DisjUnion domain
        doms = self.visit_children(node)
        return f"⊎({', '.join(doms)})"

    @handles()
    def _(self, node: ir.DomInj) -> str:
        # TODO: Determine how to pretty print DomInj
        dom_expr, = self.visit_children(node)
        return f"{dom_expr}.inj[{node.idx}]"

    @handles()
    def _(self, node: ir.Inj) -> str:
        # TODO: Determine how to pretty print Inj
        val_expr, = self.visit_children(node)
        return f"inj[{node.idx}]({val_expr})"

    @handles()
    def _(self, node: ir.Match) -> str:
        # TODO: Determine how to pretty print Match
        scrut_expr, branches_expr = self.visit_children(node)
        return f"match {scrut_expr} with ..."

    @handles()
    def _(self, node: ir.Restrict) -> str:
        # TODO: Determine how to pretty print Restrict domain
        domain_expr, pred_expr = self.visit_children(node)
        return f"{domain_expr}|{pred_expr}"

    @handles()
    def _(self, node: ir.Quotient) -> str:
        # TODO: Determine how to pretty print Quotient domain
        domain_expr, eqrel_expr = self.visit_children(node)
        return f"{domain_expr}/~{eqrel_expr}"

    ## Funcs (i.e., containers)
    @handles()
    def _(self, node: ir.Tabulate) -> str:
        dom_expr, fun_node = node._children
        dom_expr_str = self.visit(dom_expr)
        # Lambda returns (var_name, body_str) tuple
        var_name, body_str = self.visit(fun_node)
        return f"{{{body_str} | {var_name} ∈ {dom_expr_str}}}"

    @handles()
    def _(self, node: ir.DomOf) -> str:
        func_expr, = self.visit_children(node)
        return f"dom({func_expr})"

    @handles()
    def _(self, node: ir.ImageOf) -> str:
        # TODO: Determine how to pretty print ImageOf
        func_expr, = self.visit_children(node)
        return f"img({func_expr})"

    @handles()
    def _(self, node: ir.Apply) -> str:
        func_expr, arg_expr = self.visit_children(node)
        return f"{func_expr}({arg_expr})"

    @handles()
    def _(self, node: ir.ListLit) -> str:
        children = self.visit_children(node)
        return f"[{', '.join(children)}]"

    @handles()
    def _(self, node: ir.Windows) -> str:
        list_expr, size_expr, stride_expr = self.visit_children(node)
        return f"{list_expr}.windows({size_expr}, {stride_expr})"

    @handles()
    def _(self, node: ir.Tiles) -> str:
        # TODO: Determine how to pretty print Tiles - sizes and strides are tuples
        dom_expr, sizes_expr, strides_expr = self.visit_children(node)
        return f"tiles({dom_expr}, {sizes_expr}, {strides_expr})"

    @handles()
    def _(self, node: ir.Slices) -> str:
        # TODO: Determine how to pretty print Slices
        dom_expr, = self.visit_children(node)
        return f"slices({dom_expr}, {node.idx})"

    # Higher Order Operators
    @handles()
    def _(self, node: ir.Lambda) -> str:
        # TODO: Determine better heuristic for collection vs element naming
        # Collections are now FuncT or DomT, but paramT is the parameter type
        # which could be any type. This logic may need refinement.
        is_col = isinstance(node.paramT, (irT.FuncT, irT.DomT, irT.TupleT))
        if is_col:
            bv_name = f"X{self.b_num_col}"
            self.b_num_col += 1
        else:
            bv_name = f"x{self.b_num_elem}"
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

    @handles()
    def _(self, node: ir._LambdaPlaceholder) -> str:
        raise ValueError("Should not be here")

    @handles()
    def _(self, node: ir.Fold) -> str:
        # Fold signature: func: Func, fun: Lambda, init: value
        func_node, fun_node, init_node = node._children
        func_expr = self.visit(func_node)
        init_expr = self.visit(init_node)
        # Lambda returns (var_name, body_str) tuple
        var_name, body_str = self.visit(fun_node)
        # TODO: Determine how to pretty print Fold - may need better formatting
        return f"fold({func_expr}, λ{var_name}.{body_str}, {init_expr})"

    @handles()
    def _(self, node: ir.SumReduce) -> str:
        vals_expr, = self.visit_children(node)
        return f"Σ({vals_expr})"

    @handles()
    def _(self, node: ir.ProdReduce) -> str:
        vals_expr, = self.visit_children(node)
        return f"Π({vals_expr})"

    @handles()
    def _(self, node: ir.Forall) -> str:
        domain_node, fun_node = node._children
        domain_str = self.visit(domain_node)
        # Lambda returns (var_name, body_str) tuple
        var_name, body_str = self.visit(fun_node)
        # Multi-line format: context on first line, body indented on next line
        return f"∀ {var_name} ∈ {domain_str}:\n    {body_str}"

    @handles()
    def _(self, node: ir.Exists) -> str:
        domain_node, fun_node = node._children
        domain_str = self.visit(domain_node)
        # Lambda returns (var_name, body_str) tuple
        var_name, body_str = self.visit(fun_node)
        return f"∃ {var_name} ∈ {domain_str}:\n    {body_str}"

    @handles()
    def _(self, node: ir.AllDistinct) -> str:
        vals_expr, = self.visit_children(node)
        return f"distinct({vals_expr})"

    @handles()
    def _(self, node: ir.AllSame) -> str:
        vals_expr, = self.visit_children(node)
        return f"distinct({vals_expr})"


#"⊎" disjoint union
#"×"cartesian product