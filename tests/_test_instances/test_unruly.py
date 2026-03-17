import puzzlespec as ps
from puzzlespec.puzzles import get_puzzle
from puzzlespec.libs import optional as opt
from puzzlespec.backends import SMTBackend
import typing as tp

Unruly = get_puzzle("unruly")

def t0():
    print(Unruly.pretty())
    params = Unruly.params
    assert 'nR' in params
    assert 'nC' in params
    gen_vars = Unruly.gen_vars
    assert 'givens' in gen_vars
    decision_vars = Unruly.decision_vars
    assert 'color' in decision_vars
    #assert len(Unruly.param_constraints.node._children)==4
    #assert len(Unruly.gen_constraints.node._children)==2
    #assert len(Unruly.decision_constraints.node._children)==5
    #assert len(Unruly.constant_constraints.node._children)==0

    # Returns a new ruleset object with concretized parameters. (Unruly object is unmodified)
    #print("Param constraints!")
    #print(Unruly.pretty(Unruly.param_constraints.node))
    #print("Gen constraints!")
    #print(Unruly.pretty(Unruly.gen_constraints.node))
    #print("Decision constraints!")
    #print(Unruly.pretty(Unruly.decision_constraints.node))

#t0()
def t1():
    Unruly.pretty_print()
    print("*"*70)
    opt = Unruly.optimize()
    opt.pretty_print()
    #Sudoku.pretty()

    print("SETTING PARAMETERS")
    cs = ps.VarSetter(Unruly)
    # Set parameters
    cs.nR = 4
    cs.nC = 4
    unruly44 = cs.build()
    unruly44.pretty()
    assert 'nR' not in unruly44.params
    assert 'nc' not in unruly44.params

    # Change game into clue setter mode
    # helper function to set the clues
    # 1 1 0 0 
    # 0 1 0 1
    # 0 0 1 1
    # 1 1 0 0
    #
    # 1 1 X X
    # 0 X 0 X
    # 0 X X X
    # X X X X
    return
    print("SETTING CLUES")
    cs = ps.VarSetter(unruly44)
    clues = "WW..B.B.B......."
    # clue setter mode has access to all the gen_var variables as attributes
    # initialize all the given_vals to be 0 and given_mask to be false
    cs.num_clues = 5
    BW_dom, BW = ps.make_enum('B', 'W')
    optT = BW_dom.T.carT
    def _get(rc: tp.Tuple[int, int]):
        r, c = rc
        idx = r*4+c
        v = clues[idx]
        match (v):
            case '.':
                return optT.make_sum(None)
            case 'B':
                return optT.make_sum(BW.B)
            case 'W':
                return optT.make_sum(BW.W)
        return v
    cs.givens.set_lam(_get)
    instance = cs.build()
    instance.pretty()

    #print("GENERATING SMT")
    #backend = SMTBackend(instance)
    #smt = backend.generate()
t1()