from ...compiler.dsl import ir, ast
from ...libs import std
import typing as tp
#class Tactic:
#    def run(self, goal: ir.Node, wits: tp.Set[ir.Node]) -> tp.List[Action]:
#        raise NotImplementedError()
#
#class WitTactic:
#    def run(self, goal: ir.Node, wits: tp.Set[ir.Node]):
#        matches = self.match(wits)
#        if matches == []:
#            return matches
#        matches = self.precondition(matches)
#        if matches == []:
#            return matches        
#        actions = self.action(matches)
#        assert len(actions) == len(matches)
#        return actions
 #class Gt0_To_NE0(WitTactic):
#    # (0 < b) -> (b != 0)
#    def match(self, wits: tp.Set[ir.Node]):
#        matches = []
#        for wit in wits:
#            if isinstance(wit, ir.Lt):
#                T, a, b = wit.children
#                if a == ir.Lit(ir.IntT(), val=0):
#                    # Matched!
#                    matches.append((b,))
#        return matches
#
#    # Filters matches
#    def precondition(self, matches):
#        return matches
#
#    def action(self, matches):
#        actions = []
#        for match in matches:
#            b = match[0]
#            pred = (ast.wrap(b) !=0).node
#            actions.append(AddWitness(pred))
#        return actions

def open_lambda(lam: ir.LambdaHOAS, mvar: ir.MetaVar) -> ir.Node:
    def _open(node: ir.Node):
        if isinstance(node, ir.BoundVarHOAS) and node.name==lam.bv_name:
            return mvar
        children = [_open(c) for c in node.children]
        return node.replace(*children)
    return _open(lam.body)

def substitute(node: ir.Node, env: tp.Mapping[int, ir.Node]) -> ir.Node:
    if isinstance(node, ir.MetaVar):
        assert node.id in env
        return env[node.id]
    new_children = [substitute(c, env) for c in node.children]
    return node.replace(*new_children)

class Tactic:
    def __init__(
        self,
        doms,
        premises,
        conclusions
    ):  
        self.bv_doms = doms
        self.p = premises
        self.q = conclusions

    def __repr__(self):
        s = ",\n".join(f"{i}: {d}" for i, d in enumerate(self.bv_doms))
        s = s+f"\nP: {self.p}"
        s = s+f"\nQ: {self.q}"
        return s
    
    @classmethod
    def make(cls, fall: ir.Node | ast.Expr):
        if isinstance(fall, ast.Expr):
            fall = fall.node
        fall = ast.wrap(fall).simplify().node
        def _unwrap(_fall: ir.Node, id: int):
            if isinstance(_fall, ir.Implies):
                _, p, q = _fall.children
                return (), (p, q)
            elif isinstance(_fall, ir.Forall):
                _, lam = _fall.children
                dom = ast.wrap(lam).domain.node
                mvar = ir.MetaVar(id)
                body = open_lambda(lam, mvar)
                doms, pq = _unwrap(body, id+1)
                return (dom, *doms), pq
            else:
                raise ValueError(f"Cannot make tactic out of:\n{fall}")
        doms, (p, q) = _unwrap(fall, 0)
        return cls(doms, p, q)

    def apply_backward(self, goal: ir.Node):
        # Pattern match the conclusion
        env = match_template(goal, self.q, {})
        if env is None:
            return None
        assert len(env)==len(self.bv_doms)
        doms = [substitute(dom, env) for dom in self.bv_doms]
        guard = std.all([ast.wrap(dom).contains(ast.wrap(env[i])) for i, dom in enumerate(doms)]).node
        p = substitute(self.p, env)
        return [p, guard]
        
def match_template(val: ir.Node, template: ir.Node, env):
    if isinstance(template, ir.MetaVar):
        if template.id in env:
            if val != env[template.id]:
                return None
        else:
            env = {**env, template.id: val}
        return env
    if type(val) == type(template) and val.field_dict == template.field_dict:
    #if type(val) == type(template):
        envs = [match_template(vc, tc, env) for vc, tc in zip(val.children, template.children)]
        env = {}
        for e in envs:
            if e is None:
                return None
            for id, v in e.items():
                if id in env:
                    if env[id] != v:
                        return None
                else:
                    env[id] = v
        return env
    return None
 