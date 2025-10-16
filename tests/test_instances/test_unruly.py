from ast import Pass
from puzzlespec import get_puzzle
#from puzzlespec import set_clues
from puzzlespec.compiler.dsl import ir, ir_types as irT
from puzzlespec.compiler.passes import Context, PassManager, analyses as A, transforms as T
import numpy as np

Sudoku = get_puzzle("sudoku")
Unruly = get_puzzle("unruly")

def t0():
    print(Unruly.pretty(dag=False))
    print(Unruly.pretty(dag=True))
    print(Sudoku.pretty(dag=False))
    print(Sudoku.pretty(dag=True))
    params = Unruly.params
    assert 'nR' in params
    assert 'nC' in params
    gen_vars = Unruly.gen_vars
    assert 'given_mask' in gen_vars
    assert 'given_vals' in gen_vars
    decision_vars = Unruly.decision_vars
    assert 'color' in decision_vars
    # Returns a new ruleset object with concretized parameters. (Unruly object is unmodified)
    assert len(Unruly.param_constraints.node._children)==4
    assert len(Unruly.gen_constraints.node._children)==0
    assert len(Unruly.decision_constraints.node._children)==3

    print("Param constraints!")
    print(Unruly.pretty(Unruly.param_constraints))
    print("Gen constraints!")
    print(Unruly.pretty(Unruly.gen_constraints))
    print("Decision constraints!")
    print(Unruly.pretty(Unruly.decision_constraints))

    game = Unruly.set_params(nR=4)
    assert 'nC' in game.params
    assert 'nR' not in game.params
    game = game.set_params(nC=4)
    assert 'nC' not in game.params
    assert 'nR' not in game.params

t0()

def t1():
    game = Unruly.set_params(nR=4, nC=4)
    assert game.params == {}
    gen_vars = game.gen_vars
    assert 'given_mask' in gen_vars
    assert 'given_vals' in gen_vars

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
    
    clues = "11..0.0.0......."
    with game.clue_setter() as cs:
        # clue setter mode has access to all the gen_var variables as attributes
        # initialize all the given_vals to be 0 and given_mask to be false
        cs.given_vals.set(np.zeros(shape=(4,4)))
        cs.given_mask.set(np.zeros(shape=(4,4)))
        for i, v in enumerate(clues):
            r = i // 4
            c = i % 4
            if v != '.':
                v = int(v)
                cs.given_mask[(r,c)] = True
                cs.given_vals[(r,c)] = v
    
    # This will do the final substituiton of the genvars
    game_with_clues = cs.build()