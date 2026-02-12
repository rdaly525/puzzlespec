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
#                T, a, b = wit._children
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
        children = [_open(c) for c in node._children]
        return node.replace(*children)
    return _open(lam.body)

def substitute(node: ir.Node, env: tp.Mapping[int, ir.Node]) -> ir.Node:
    if isinstance(node, ir.MetaVar):
        assert node.id in env
        return env[node.id]
    new_children = [substitute(c, env) for c in node._children]
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
    
    @classmethod
    def make(cls, fall: ir.Node | ast.Expr):
        if isinstance(fall, ast.Expr):
            fall = fall.node
        assert isinstance(fall, ir.Forall)
        _, lam = fall._children
        bv_dom = ast.wrap(lam).domain.node
        mvar = ir.MetaVar(0)
        body = open_lambda(lam, mvar)
        assert isinstance(body, ir.Implies)
        _, p, q = body._children
        return cls([bv_dom], p, q)

    def apply_backward(self, goal: ir.Node):
        # Pattern match the conclusion
        env = match_template(goal, self.q, {})
        if env is None:
            return None
        assert len(env)==len(self.bv_doms)
        guard = std.all([ast.wrap(dom).contains(ast.wrap(env[i])) for i, dom in enumerate(self.bv_doms)]).node
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
        envs = [match_template(vc, tc, env) for vc, tc in zip(val._children, template._children)]
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
 