from puzzlespec import PuzzleSpec, get_puzzle
#from puzzlespec import set_clues
from puzzlespec.compiler.dsl import ir, setter, ast
from puzzlespec.compiler.dsl.libs import std, optional as opt
from puzzlespec.compiler.passes import Context, PassManager, analyses as A, transforms as T
import numpy as np

#Sudoku = get_puzzle("sudoku")
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

    game = Unruly.set_params(nR=4)
    assert 'nC' in game.params
    assert 'nR' not in game.params
    game = game.set_params(nC=4)
    assert 'nC' not in game.params
    assert 'nR' not in game.params

def t1():
    cs = setter.VarSetter(Unruly)
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
    print("CLUE SETTER MODE")
    cs = setter.VarSetter(unruly44)
    clues = "11..0.0.0......."
    # clue setter mode has access to all the gen_var variables as attributes
    # initialize all the given_vals to be 0 and given_mask to be false
    cs.num_clues = 5
    BW_dom, BW_enum = std.Enum('B', 'W')
    optBW = opt.Optional(BW_dom)
    optT = optBW.T.carT
    def _get(r, c):
        idx = r*4+c
        v = clues[idx]
        match (v):
            case '.':
                return optT.make_sum(None)
            case '1':
                return optT.make_sum(BW_enum.B)
            case '0':
                return optT.make_sum(BW_enum.W)
        return v
    cs.givens.set_lam(_get)
    instance = cs.build()
    print(instance.pretty())

t1()