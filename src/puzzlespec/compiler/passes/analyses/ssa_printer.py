from __future__ import annotations

from multiprocessing import Value
import typing as tp

from ..pass_base import Analysis, AnalysisObject, Context, handles
from .sym_table import SymTableEnv_
from .type_inference import TypeEnv_, TypeValues
from ...dsl import ir, ir_types as irT
from ...dsl.envs import SymTable, TypeEnv

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


class SSAResult(AnalysisObject):
    def __init__(self, text):
        self.text = text


class SSAPrinter(Analysis):
    """
    Creates a python AST object that is a 'serialization' of a SpecObject
    This will be in SSA form and will look something like:

    """

    requires = (SymTableEnv_, TypeValues)  
    produces = (SSAResult,)  
    name = "ssa_printer"

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        """Main entry point for the analysis pass."""
        self.tenv = ctx.get(TypeValues).mapping
        self.sym: SymTable = ctx.get(SymTableEnv_).sym
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
    
    @handles(ir._Param, ir._BoundVarPlaceholder, ir._LambdaPlaceholder, mark_invalid=True)
    def _(self, node: ir._Param) -> tp.Any:
        ...
