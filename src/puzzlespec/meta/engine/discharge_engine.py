from __future__ import annotations
#from puzzlespec import make_enum, var, func_var, Unit, Int, U, PuzzleSpecBuilder, VarSetter
#from puzzlespec.libs import std
#from puzzlespec.libs import optional as opt, topology as topo, nd
from ...compiler.dsl import ir, ast
from .tactic import Tactic
import typing as tp
from dataclasses import dataclass

class Action: pass
class Engine: pass

@dataclass
class Justification:
    tactic: Tactic | tp.Literal['And', 'Or']
    kind: tp.Literal['and', 'or']
    goals: tp.Tuple[GoalNode]
    parent: GoalNode


    @property
    def status(self):
        gs = [g.status for g in self.goals]
        if self.kind=='and':
            if all(s == "Proven" for s in gs):
                return "Proven"
            if any(s == "Disproven" for s in gs):
                return "Disproven"
        else:
            if all(s == "Disproven" for s in gs):
                return "Disproven"
            if any(s == "Proven" for s in gs):
                return "Proven"
 
    def __post_init__(self):
        for g in self.goals:
            g.parents.append(self)

@dataclass
class GoalNode:
    goal: ir.Node
    kind: tp.Literal["base", "and", "or"]
    facts: tp.Tuple[ir.Node]
    status: tp.Literal["New", "Expanded", "Proven", "Disproven", "Failed"] = "New"
    def __post_init__(self):
        self.goal = ast.wrap(self.goal).simplify().node
        self.justs: tp.List[Justification] = []
        self.parents: tp.List[GoalNode] = []

    def add_justification(self, just: Justification):
        self.justs.append(just)

    def __eq__(self, other):
        if not isinstance(other, GoalNode):
            return False
        return self.goal==other.goal

    

class DischargeEngine(Engine):
    def __init__(self, *tactics: Tactic, verbose=0, max_iter=10):
        self.verbose=verbose
        self.tactics = tactics
        self.max_iter = max_iter

    def build_goal(self, goal: ir.Node, facts):
        return GoalNode(goal, kind=None, facts=facts)

    def prove_backwards(self, goal, wits: tp.List[ir.Node]) -> str:
        assert isinstance(goal, ir.Node)
        assert all(isinstance(wit, ir.Node) for wit in wits)
        self.root_wits = set([ast.wrap(w).simplify().node for w in wits])
        goal = ast.wrap(goal).simplify().node
        self.root_goal = self.build_goal(goal, self.root_wits)
        self.work: tp.List[GoalNode] = []
        self.work.append(self.root_goal)
        while len(self.work) > 0:
            goal = self.work.pop()
            if goal.status == "New":
                self.prove_goal(goal)
        return self.root_goal.status

    def prove_goal(self, goalN: GoalNode):
        print(f"Working on: {goalN.goal}")
        goal = goalN.goal
        if goal == ir.Lit(ir.BoolT(), True):
            goalN.status = "Proven"
        elif goal in goalN.facts:
            goalN.status = "Proven"
        elif isinstance(goal, ir.Conj):
            children = [self.build_goal(c) for c in goal._children[1:]]
            goalN.status = "Expanded"
            goalN.kind = "and"
            for c in children:
                self.work.append(c)
            # Create justification
            just = Justification('And', 'and', tuple(children), goalN)
            goalN.add_justification(just)
        elif isinstance(goal, ir.Disj):
            children = [self.build_goal(c) for c in goal._children[1:]]
            goalN.status = "Expanded"
            goalN.kind = "or"
            # Only add 1st branch
            self.work.append(children[0])
            # Create justification
            just = Justification('Or', 'or', tuple(children), goalN)
            goalN.add_justification(just)
        else:
            goalN.kind = "base"
            # Try proving with tactics
            progress = self.prove_backwards_tactics(goalN)
            if not progress:
                raise ValueError("Not proved :(")
        print(f"  {goalN.status}")
        if goalN.status == "Proven":
            self.propogate_justifications(goalN)
    
    def propogate_justifications(self, goalN: GoalNode):
        assert goalN.status == "Proven"
        for j in goalN.parents:
            assert isinstance(j, Justification)
            statuses = [g.status for g in j.goals]
            if j.kind=="and":
                if all(s=='Proven' for s in statuses):
                    pgoal = j.parent
                    pgoal.status = "Proven"
                    self.propogate_justifications(pgoal)
            else:
                raise NotImplementedError()
            

    def prove_backwards_tactics(self, goalN: GoalNode):
        assert goalN.kind=='base'
        progress = False
        for t in self.tactics:
            sub_goals = t.apply_backward(goalN.goal)
            if sub_goals is None:
                continue
            # Applied tactic successfully!
            # Add a justification edge.
            sub_goals = [self.build_goal(g, list(goalN.facts)) for g in sub_goals]
            for g in sub_goals:
                self.work.append(g)
            just = Justification(t, 'and', tuple(sub_goals), goalN)
            goalN.status = "Expanded"
            goalN.add_justification(just)
            progress=True
            break
        if not progress:
            goalN.status = "Failed"
        return progress
            


    # 

    #    for i in range(self.max_iter):
    #        if self.verbose:
    #            print(f"Goal: {goal}")
    #            print("Wits:")
    #            for wit in cur_wits:
    #                print(f"  {wit}")
    #        # 'rfl'-like tactic
    #        if isinstance(goal, ir.Lit):
    #            if goal.val:
    #                return "Proven"
    #            else:
    #                return "Disproven"
    #        if goal in cur_wits:
    #            return 'Proven'

    #        new_wits = set()
    #        progress = False
    #        for t in self.tactics:
    #            actions = t.run(goal, self.wits)
    #            for action in actions:
    #                progress = True
    #                if isinstance(action, AddWitness):
    #                    new_wits.add(ast.wrap(action.pred).simplify().node)
    #                if isinstance(action, ReplaceGoal):
    #                    goal = action.goal
    #                else:
    #                    raise NotImplementedError()
    #        if not progress:
    #            break
    #        cur_wits = new_wits
    #    return "Not proven!"

