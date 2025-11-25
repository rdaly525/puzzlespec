from __future__ import annotations

import typing as tp


from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir
from ..envobj import EnvsObj, TypeEnv, SymTable

class PrettyPrintedExpr(AnalysisObject):
    def __init__(self, text: str):
        self.text = text

def subscript(n: int) -> str:
    # handle mutliple digits
    subs = "₀₁₂₃₄₅₆₇₈₉"
    return "".join(subs[int(d)] for d in str(n))
#
#def superscript(n: int) -> str:
#    table = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
#    return "".join(table[d] for d in str(n))

class PrettyPrinterPass(Analysis):
    """Produce a human-readable string representation of expressions using infix notation.
    
    Converts expressions like Eq(Mod(Param(), Lit()), Lit()) into readable form like "nR % 2 == 0".
    Uses mathematical notation with explicit parentheses and supports:
    - Infix operators for arithmetic and comparisons
    - Variable indexing for array access
    - Mathematical symbols for quantifiers (∀, ∃, Σ)
    - Compact single-line set builder notation for Map operations
    - Smart bound variable names (X0, X1 for collections; x0, x1 for simple types, reused in sibling scopes)
    - Multi-line formatting for quantifiers (context on first line, body indented)
    - Multi-line formatting for Conj/Disj using ∩/∪ symbols with line breaks
    
    The result is stored in the context as a `PrettyPrintedExpr` object.
    """

    requires = (EnvsObj,)
    produces = (PrettyPrintedExpr,)
    name = "pretty_printer"

    def visit(self, node):
        raise NotImplementedError(f"{node.__class__.__name__} not implemented in PrettyPrinterPass")
        # All node kinds have a custom visit

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        # Get analysis results
        envs = ctx.get(EnvsObj)
        self.tenv: TypeEnv = envs.tenv
        self.sym: SymTable = envs.sym
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
        s += "Constraints:\n"
        s += constraint_text
        print("\n"+s+"\n")
        return PrettyPrintedExpr(s)

    ##############################
    ## Core-level IR Type nodes 
    ##############################

    @handles(ir.UnitT)
    def _(self, node: ir.UnitT) -> str:
        return str(node)

    @handles(ir.BoolT)
    def _(self, node: ir.BoolT) -> str:
        return str(node)

    @handles(ir.IntT)
    def _(self, node: ir.IntT) -> str:
        return str(node)

    @handles(ir.EnumT)
    def _(self, node: ir.EnumT) -> str:
        return str(node)

    @handles(ir.TupleT)
    def _(self, node: ir.TupleT) -> str:
        elem_strs = self.visit_children(node)
        return "⨯".join(elem_strs)

    @handles(ir.SumT)
    def _(self, node: ir.SumT) -> str:
        elem_strs = self.visit_children(node)
        return "⊎".join(elem_strs)

    #@handles(ir.ArrowT)
    #def _(self, node: ir.ArrowT) -> str:
    #    arg_str, res_str = self.visit_children(node)
    #    return f"{arg_str} -> {res_str}"

    @handles(ir.DomT)
    def _(self, node: ir.DomT) -> str:
        factor_strs = self.visit_children(node)
        if len(factor_strs) == 1:
            car_str = factor_strs[0]
        else:
            car_str = "⨯".join(factor_strs)
        return f"Dom[{car_str}]"

    @handles(ir.LambdaT)
    def _(self, node: ir.LambdaT) -> str:
        argT, resT = node._children
        is_col = isinstance(argT, (ir.PiT, ir.DomT))
        if is_col:
            bv_name = f"X{self.b_num_col}"
            self.b_num_col += 1
        else:
            bv_name = f"x{self.b_num_elem}"
            self.b_num_elem += 1
        self.b_names.append(bv_name)
        resT_str = self.visit(resT)
        # pop the stack
        self.b_names.pop()
        if is_col:
            self.b_num_col -= 1
        else:
            self.b_num_elem -= 1
        return bv_name, resT_str

    @handles(ir._LambdaTPlaceholder)
    def _(self, node: ir._LambdaTPlaceholder) -> str:
        assert 0
        bv, resT = self.visit_children(node)
        return (bv, resT)

    @handles(ir.PiT)
    def _(self, node: ir.PiT):
        dom_str, (bv_name, resT_str) = self.visit_children(node)
        return f"Pi[{dom_str} -> {bv_name}: {resT_str}]"
    
    @handles(ir.ApplyT)
    def _(self, node: ir.ApplyT):
        piT_str, arg_str = self.visit_children(node)
        return f"{piT_str}({arg_str})"

    ##############################
    ## Core-level IR Value nodes (Used throughout entire compiler flow)
    ##############################

    @handles(ir.VarRef)
    def _(self, node: ir.VarRef) -> str:
        e = self.sym[node.sid]
        name, role = e.name, e.role
        T = self.tenv[node.sid]
        T_str = self.visit(T)
        if role=='P':
            self.p_to_T[name] = T_str
        elif role=='G':
            self.g_to_T[name] = T_str
        elif role=='D':
            self.d_to_T[name] = T_str
        return name

    @handles(ir.BoundVar)
    def _(self, node: ir.BoundVar) -> str:
        return self.b_names[-(node.idx+1)]

    @handles(ir.Unit)
    def _(self, node: ir.Unit) -> str:
        return "tt"

    @handles(ir.Lambda)
    def _(self, node: ir.Lambda) -> str:
        paramT = node.T.argT
        is_col = isinstance(paramT, (ir.PiT, ir.DomT))
        if is_col:
            bv_name = f"X{self.b_num_col}"
            self.b_num_col += 1
        else:
            bv_name = f"x{self.b_num_elem}"
            self.b_num_elem += 1
        self.b_names.append(bv_name)
        _, body_txt = self.visit_children(node)  # Skip type at index 0
        # pop the stack
        self.b_names.pop()
        if is_col:
            self.b_num_col -= 1
        else:
            self.b_num_elem -= 1
        return bv_name, body_txt

    @handles(ir.Lit)
    def _(self, node: ir.Lit) -> str:
        if isinstance(node.T, ir.BoolT):
            return '𝕋' if node.val else '𝔽'
        return str(node.val)

    @handles(ir.Eq)
    def _(self, node: ir.Eq) -> str:
        _, left, right = self.visit_children(node)  # Skip type at index 0
        return f"({left} = {right})"

    @handles(ir.Lt)
    def _(self, node: ir.Lt) -> str:
        _, left, right = self.visit_children(node)  # Skip type at index 0
        return f"({left} < {right})"

    @handles(ir.LtEq)
    def _(self, node: ir.LtEq) -> str:
        _, left, right = self.visit_children(node)  # Skip type at index 0
        return f"({left} ≤ {right})"

    @handles(ir.Ite)
    def _(self, node: ir.Ite) -> str:
        _, pred, t, f = self.visit_children(node)  # Skip type at index 0
        return f"({pred} ? {t} : {f})"

    @handles(ir.Not)
    def _(self, node: ir.Not) -> str:
        _, child = self.visit_children(node)  # Skip type at index 0
        return f"¬{child}"

    @handles(ir.Neg)
    def _(self, node: ir.Neg) -> str:
        _, child = self.visit_children(node)  # Skip type at index 0
        return f"(-{child})"

    @handles(ir.Div)
    def _(self, node: ir.Div) -> str:
        _, left, right = self.visit_children(node)  # Skip type at index 0
        return f"({left} // {right})"

    @handles(ir.Mod)
    def _(self, node: ir.Mod) -> str:
        _, left, right = self.visit_children(node)  # Skip type at index 0
        return f"({left} % {right})"

    def _indent_expr(self, expr: str, indent: str = "    ") -> str:
        """Helper function to indent an expression, handling both single-line and multi-line cases.
        
        Args:
            expr: The expression string to indent
            indent: The indentation string to use (default: 4 spaces)
        
        Returns:
            The expression with proper indentation applied to all lines.
        """
        if '\n' in expr:
            # Expression is multi-line, indent each line
            lines = expr.split('\n')
            indented_lines = [f"{indent}{line}" for line in lines]
            return '\n'.join(indented_lines)
        else:
            # Expression is single-line, just indent it
            return f"{indent}{expr}"

    def _format_variadic_multiline(
        self, 
        children_strs: list[str], 
        prefix: str, 
        empty_default: str | None = None,
        single_default: str | None = None,
        separator: str | None = None,
        suffix: str | None = None
    ) -> str:
        """Helper function to format variadic nodes with multi-line support.
        
        Args:
            children_strs: List of child string representations
            prefix: Symbol/prefix to use on the first line
            empty_default: Value to return if children_strs is empty (if None, uses prefix)
            single_default: Value to return if children_strs has one element (if None, returns the element)
            separator: Optional separator to append to each child (except the last), e.g. ","
            suffix: Optional suffix to append after all children, e.g. ")"
        
        Returns:
            Formatted string with prefix on first line and indented children on subsequent lines.
        """
        if not children_strs:
            return empty_default if empty_default is not None else prefix
        if len(children_strs) == 1:
            if single_default is not None:
                result = single_default
            else:
                result = children_strs[0]
                # If we have both prefix and suffix, wrap the single element
                if prefix and suffix:
                    result = f"{prefix}{result}{suffix}"
            return result
        
        # Multi-line format with prefix symbol, properly indent multi-line children
        indented_children = []
        for i, child_str in enumerate(children_strs):
            child_formatted = self._indent_expr(child_str)
            
            # Add separator if provided (except for last element)
            if separator and i < len(children_strs) - 1:
                child_formatted += separator
            
            indented_children.append(child_formatted)
        
        result = f"{prefix}\n" + "\n".join(indented_children)
        if suffix:
            result += f"\n{suffix}"
        return result

    # Variadic
    @handles(ir.Conj)
    def _(self, node: ir.Conj) -> str:
        children_strs = self.visit_children(node)[1:]  # Skip type at index 0
        if len(children_strs) == 2:
            return f"({children_strs[0]} ∧ {children_strs[1]})"
        return self._format_variadic_multiline(children_strs, "∩", empty_default='𝕋')

    @handles(ir.Disj)
    def _(self, node: ir.Disj) -> str:
        children_strs = self.visit_children(node)[1:]  # Skip type at index 0
        if len(children_strs) == 2:
            return f"({children_strs[0]} ∨ {children_strs[1]})"
        return self._format_variadic_multiline(children_strs, "∪", empty_default='𝔽')

    @handles(ir.Sum)
    def _(self, node: ir.Sum) -> str:
        children_strs = self.visit_children(node)[1:]  # Skip type at index 0
        if len(children_strs) == 2:
            return f"({children_strs[0]} + {children_strs[1]})"
        sum_str = ", ".join(c for c in children_strs)
        return f"Σ({sum_str})"

    @handles(ir.Prod)
    def _(self, node: ir.Prod) -> str:
        children_strs = self.visit_children(node)[1:]  # Skip type at index 0
        if len(children_strs) == 2:
            return f"({children_strs[0]} * {children_strs[1]})"
        p_str = ", ".join(c for c in children_strs)
        return f"Π({p_str})"
    
    ## Domains
    @handles(ir.Universe)
    def _(self, node: ir.Universe) -> str:
        carT_str = self.visit(node.T.carT)
        return f"𝕌({carT_str})"

    @handles(ir.Fin)
    def _(self, node: ir.Fin) -> str:
        _, n_expr = self.visit_children(node)  # Skip type at index 0
        return f"Fin({n_expr})"

    @handles(ir.EnumLit)
    def _(self, node: ir.EnumLit) -> str:
        return f"{node.T.name}.{node.label}"

    @handles(ir.Card)
    def _(self, node: ir.Card) -> str:
        _, domain_expr = self.visit_children(node)  # Skip type at index 0
        return f"#{domain_expr}"

    @handles(ir.IsMember)
    def _(self, node: ir.IsMember) -> str:
        _, domain_expr, val_expr = self.visit_children(node)  # Skip type at index 0
        return f"({val_expr} ∈ {domain_expr})"

    ## Cartesian Products
    @handles(ir.CartProd)
    def _(self, node: ir.CartProd) -> str:
        doms = self.visit_children(node)[1:]  # Skip type at index 0
        return "(" + "×".join(doms) + ")"

    @handles(ir.DomProj)
    def _(self, node: ir.DomProj) -> str:
        # TODO: Determine how to pretty print DomProj
        _, dom_expr = self.visit_children(node)  # Skip type at index 0
        return f"π{subscript(node.idx)}⟦{dom_expr}⟧"

    # Collections - Tuple nodes
    @handles(ir.TupleLit)
    def _(self, node: ir.TupleLit) -> str:
        elements = self.visit_children(node)[1:]  # Skip type at index 0
        return self._format_variadic_multiline(
            elements, 
            prefix="(", 
            empty_default="()",
            separator=",",
            suffix=")"
        )

    @handles(ir.Proj)
    def _(self, node: ir.Proj) -> str:
        _, tup_expr = self.visit_children(node)  # Skip type at index 0
        return f"π{subscript(node.idx)}⟨{tup_expr}⟩"

    @handles(ir.DisjUnion)
    def _(self, node: ir.DisjUnion) -> str:
        doms = self.visit_children(node)[1:]  # Skip type at index 0
        return "(" + "⊎".join(doms) + ")"

    @handles(ir.DomInj)
    def _(self, node: ir.DomInj) -> str:
        _, dom_expr = self.visit_children(node)  # Skip type at index 0
        return f"ι{subscript(node.idx)}⟦{dom_expr}⟧"

    @handles(ir.Inj)
    def _(self, node: ir.Inj) -> str:
        _, val_expr = self.visit_children(node)  # Skip type at index 0
        return f"ι{subscript(node.idx)}⟨{val_expr}⟩"

    @handles(ir.Match)
    def _(self, node: ir.Match) -> str:
        _, scrut_node, branches = node._children
        scrut_expr = self.visit(scrut_node)
        assert isinstance(branches, ir.TupleLit)
        assert all(isinstance(branch, (ir.Lambda, ir._LambdaPlaceholder)) for branch in branches._children[1:])
        branch_exprs = [self.visit(branch) for branch in branches._children[1:]]
        branch_argTs = []
        for branch_lam in branches._children[1:]:
            argT = self.visit(branch_lam.T.argT)
            branch_argTs.append(argT)
        #branch_exprs_str = ", ".join(f"(λ {var_name}. {body})" for var_name, body in branch_exprs)
        branch_strs = [f"{var_name}: {argT} = {body}" for argT, (var_name, body) in zip(branch_argTs, branch_exprs)]
        return f"match {scrut_expr}:\n" + "\n".join(self._indent_expr(bs) for bs in branch_strs) + "\n"

    @handles(ir.Restrict)
    def _(self, node: ir.Restrict) -> str:
        _, domain_expr, (var_name, pred_expr) = self.visit_children(node)  # Skip type at index 0
        return f"{{{var_name} ∈ {domain_expr} | {pred_expr}}}"

    @handles(ir.Forall)
    def _(self, node: ir.Forall) -> str:
        _, domain_expr, (var_name, body_expr) = self.visit_children(node)  # Skip type at index 0
        # Multi-line format: context on first line, body indented on next line
        # If body_expr is multi-line (e.g., nested Forall/Exists), indent all lines
        body_formatted = self._indent_expr(body_expr)
        return f"∀ {var_name} ∈ {domain_expr}:\n{body_formatted}"

    @handles(ir.Exists)
    def _(self, node: ir.Exists) -> str:
        _, domain_expr, (var_name, body_expr) = self.visit_children(node)  # Skip type at index 0
        # Multi-line format: context on first line, body indented on next line
        # If body_expr is multi-line (e.g., nested Forall/Exists), indent all lines
        body_formatted = self._indent_expr(body_expr)
        return f"∃ {var_name} ∈ {domain_expr}:\n{body_formatted}"

    ## Funcs (i.e., containers)
    @handles(ir.Map)
    def _(self, node: ir.Map) -> str:
        piT_str, dom_expr, (var_name, body_str) = self.visit_children(node)  # Skip type at index 0
        # Lambda returns (var_name, body_str) tuple
        return f"[{body_str} | {var_name} ∈ {dom_expr}]"

    @handles(ir.Image)
    def _(self, node: ir.Image) -> str:
        _, func_expr = self.visit_children(node)  # Skip type at index 0
        return f"{func_expr}[𝕏]"

    @handles(ir.Apply)
    def _(self, node: ir.Apply) -> str:
        _, func_expr, arg_expr = self.visit_children(node)  # Skip type at index 0
        return f"{func_expr}({arg_expr})"

    @handles(ir.ListLit)
    def _(self, node: ir.ListLit) -> str:
        children = self.visit_children(node)[1:]  # Skip type at index 0
        return f"[{', '.join(children)}]"

    @handles(ir.Fold)
    def _(self, node: ir.Fold) -> str:
        # Fold signature: func: Func, fun: Lambda, init: value
        _, func_expr, (var_name, body_str), init_expr = self.visit_children(node)  # Skip type at index 0
        # Lambda returns (var_name, body_str) tuple
        # TODO: Determine how to pretty print Fold - may need better formatting
        return f"fold({func_expr}, λ{var_name}.{body_str}, {init_expr})"

    @handles(ir.Slice)
    def _(self, node: ir.Slice) -> str:
        _, dom_expr, lo_expr, hi_expr = self.visit_children(node)  # Skip type at index 0
        return f"{dom_expr}[{lo_expr}:{hi_expr}]"

    @handles(ir.Index)
    def _(self, node: ir.Index) -> str:
        _, dom_expr, idx_expr = self.visit_children(node)  # Skip type at index 0
        return f"{{{idx_expr}}}"

    ##############################
    ## Surface-level IR nodes (Used for analysis, but can be collapsed)
    ##############################

    @handles(ir.And)
    def _(self, node: ir.And) -> str:
        _, left, right = self.visit_children(node)  # Skip type at index 0
        return f"({left} ∧ {right})"

    @handles(ir.Implies)
    def _(self, node: ir.Implies) -> str:
        _, left, right = self.visit_children(node)  # Skip type at index 0
        return f"({left} → {right})"

    @handles(ir.Or)
    def _(self, node: ir.Or) -> str:
        _, left, right = self.visit_children(node)  # Skip type at index 0
        return f"({left} ∨ {right})"

    @handles(ir.Add)
    def _(self, node: ir.Add) -> str:
        _, ltext, rtext = self.visit_children(node)  # Skip type at index 0
        return f"({ltext} + {rtext})"

    @handles(ir.Sub)
    def _(self, node: ir.Sub) -> str:
        _, left, right = self.visit_children(node)  # Skip type at index 0
        return f"({left} - {right})"

    @handles(ir.Mul)
    def _(self, node: ir.Mul) -> str:
        _, left, right = self.visit_children(node)  # Skip type at index 0
        return f"({left} * {right})"

    @handles(ir.Gt)
    def _(self, node: ir.Gt) -> str:
        _, left, right = self.visit_children(node)  # Skip type at index 0
        return f"({left} > {right})"

    @handles(ir.GtEq)
    def _(self, node: ir.GtEq) -> str:
        _, left, right = self.visit_children(node)  # Skip type at index 0
        return f"({left} ≥ {right})"

    @handles(ir.SumReduce)
    def _(self, node: ir.SumReduce) -> str:
        _, vals_expr = self.visit_children(node)  # Skip type at index 0
        return f"Σ{vals_expr}"

    @handles(ir.ProdReduce)
    def _(self, node: ir.ProdReduce) -> str:
        _, vals_expr = self.visit_children(node)  # Skip type at index 0
        return f"Π{vals_expr}"

    @handles(ir.AllDistinct)
    def _(self, node: ir.AllDistinct) -> str:
        _, vals_expr = self.visit_children(node)  # Skip type at index 0
        return f"distinct({vals_expr})"

    @handles(ir.AllSame)
    def _(self, node: ir.AllSame) -> str:
        _, vals_expr = self.visit_children(node)  # Skip type at index 0
        return f"same({vals_expr})"

    ##############################
    ## Constructor-level IR nodes (Used for construction but immediately gets transformed for spec)
    ##############################

    @handles(ir._BoundVarPlaceholder)
    def _(self, node: ir._BoundVarPlaceholder) -> str:
        T, = self.visit_children(node)
        return f"b{id(node)}"

    @handles(ir._LambdaPlaceholder)
    def _(self, node: ir._LambdaPlaceholder) -> str:
        T, bv, body = self.visit_children(node)
        return bv, body

    @handles(ir._VarPlaceholder)
    def _(self, node: ir._VarPlaceholder) -> str:
        T, = self.visit_children(node)
        return f"v{node.sid}"

#"⊎" disjoint union
#"×"cartesian product