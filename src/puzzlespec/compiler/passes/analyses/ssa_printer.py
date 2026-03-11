from __future__ import annotations

import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ..envobj import EnvsObj, SymTable
from ...dsl import ir, ast

class UsesResult(AnalysisObject):
    def __init__(self, use_cnt):
        self.use_cnt = use_cnt

class Uses(Analysis):
    produces = (UsesResult,)

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        """Main entry point for the analysis pass."""
        self.use_cnt = {root: 1}
        self.visit(root)
        return UsesResult(self.use_cnt)

    def visit(self, node: ir.Node) -> tp.Any:
        self.visit_children(node)
        for c in node._children:
            if c in self.use_cnt:
                self.use_cnt[c] += 1
            else:
                self.use_cnt[c] = 1

def print_ssa(node: ir.Node):
    text = SSAPrinter()(node, Context()).text
    print(text)

class SSAResult(AnalysisObject):
    def __init__(self, text):
        self.text = text

class SSAPrinter(Analysis):
    """
    Creates a python AST object that is a 'serialization' of a SpecObject
    This will be in SSA form and will look something like:

    """

    requires = ()  
    produces = (SSAResult,)  
    name = "ssa_printer"
    enable_memoization=False

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.tcnt = 0
        self.vcnt = 0
        self.vmap = {}
        self.decls = []
        res = self.visit(root)
        text = "\n" + "\n".join(self.decls) + "\n"
        return SSAResult(text)

    def new_var(self, node: ir.Node):
        if isinstance(node, ir.Type):
            v = f"t{self.tcnt}"
            self.tcnt += 1
        else:
            v = f"x{self.vcnt}"
            self.vcnt += 1
        return v

    def visit(self, node: ir.Node):
        if node not in self.vmap:
            cvals= self.visit_children(node)
            vname = self.new_var(node)
            fstr = ""
            if len(node.field_dict) > 0:
                fstr = "[" + ", ".join(f"{k}={v}" for k,v in node.field_dict.items()) + "]"
            cs = ", ".join(cvals)
            decl = f"{vname} = {node.__class__.__name__}{fstr}({cs})"
            decl += f" {ast.wrap(node)._freevars}"
            #decl += f" {ast.wrap(node)}"
            self.decls.append(decl)
            self.vmap[node] = vname
        return self.vmap[node]


 
class _SSAPrinter(Analysis):
    """
    Creates a python AST object that is a 'serialization' of a SpecObject
    This will be in SSA form and will look something like:

    """

    requires = ()  
    produces = (SSAResult,)  
    name = "ssa_printer"

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        self.decls = {}
        self.var_names = set()
        self.use_cnt = Uses()(root, ctx).use_cnt
        self._var_cnt={}
        constraints = [self.visit(c) for c in root._children]
        c_str = ", \n    ".join(cs for cs in constraints)
        text = "# Variables";
        for name, (T, con) in self.decls.items():
            if name in self.var_names:
                text += f"\n{name}: {T} = {con}"
        text += "\n# other vars"
        for name, (T, con) in self.decls.items():
            if name not in self.var_names:
                text += f"\n{name}: {T} = {con}"
        text += f"\nreturn ∩(\n    {c_str}\n)\n"
        print(text)
        return SSAResult(text)

    def do_use(self, node, use_s, prefix='x'):
        if node not in self.use_cnt:
            raise ValueError(f"{node} not in use_cnt")
        if self.use_cnt[node] > 1:
            var = self._new_var_name('x')
            self._add_new_decl(var, self.tenv[node], use_s)
            return var
        else:
            return use_s

    def visit(self, node: ir.Node) -> tp.Any:
        strs = self.visit_children(node)
        # Create use str
        use_s = f"{node.__class__.__name__}({', '.join(strs)})"
        return self.do_use(node, use_s)

    def _new_var_name(self, prefix: str, is_var=False):
        if is_var:
            name = prefix
            self.var_names.add(name)
        else:
            self._var_cnt.setdefault(prefix, 0)
            name = f"{prefix}{self._var_cnt[prefix]}"
            self._var_cnt[prefix] += 1
        return name

    def _add_new_decl(self, name: str, T: irT.Type_, constructor: str):
        assert name not in self.decls
        self.decls[name] = (T, constructor)

    # Literals and basic nodes
    @handles()
    def _(self, node: ir.Lit) -> tp.Any:
        """Analyze literal nodes."""
        return str(node.val)

    @handles()
    def _(self, node: ir.VarRef) -> tp.Any:
        """Analyze variable reference nodes."""
        var = self._new_var_name(self.sym.get_name(node.sid), is_var=True)
        self._add_new_decl(var, self.tenv[node], 'Var()')
        return var
 
    @handles()
    def _(self, node: ir.BoundVar) -> tp.Any:
        """Analyze bound variable nodes."""
        return f"#{node.idx}"
    
    @handles(ir.BoundVarHOAS, ir.LambdaHOAS, mark_invalid=True)
    def _(self, node: ir.Node) -> tp.Any:
        ...
