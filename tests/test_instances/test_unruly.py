from puzzlespec import get_puzzle
#from puzzlespec import set_clues
from puzzlespec.compiler.dsl import ir, ir_types as irT
from puzzlespec.compiler.passes import Context, PassManager, analyses as A, transforms as T

Unruly = get_puzzle("unruly")
def t0():
    assert Unruly.is_frozen()
    params = Unruly.params
    assert 'nR' in params
    assert 'nC' in params
    gen_vars = Unruly.gen_vars
    assert 'given_mask' in gen_vars
    assert 'given_vals' in gen_vars
    decision_vars = Unruly.decision_vars
    assert 'color' in decision_vars
    # Returns a new ruleset object with concretized parameters. (Unruly object is unmodified)
    
    game = Unruly.set_params(nR=4)
    assert 'nC' in game.params
    assert 'nR' not in game.params
    game = game.set_params(nC=4)
    assert 'nC' not in game.params
    assert 'nR' not in game.params

t0()

def t1():
    _game = Unruly.set_params(nR=4, nC=4)
    assert _game.params == {}
    _gen_vars = _game.gen_vars
    assert 'given_mask' in _gen_vars
    assert 'given_vals' in _gen_vars

    # Cannot set vals of a variable
    given_mask = _gen_vars['given_mask']
    try:
        given_mask[(0,0)] = 1
        assert False
    except:
        pass
    
    # Change game into clue setter mode
    game_gen = _game.clue_setter()
    gen_vars = game_gen.gen_vars
    assert gen_vars is not _gen_vars
    given_mask = gen_vars['given_mask']
    given_vals = gen_vars['given_mask']

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
    for i, v in enumerate(clues):
        r = i // 4
        c = i % 4
        if v != '.':
            v = int(v)
            game_gen += given_mask[(r,c)] == True
            game_gen += given_vals[(r,c)] == v
        else:
            game_gen += given_mask[(r,c)] == False




def t2():
    ctx = Context()
    ctx.add(A.TypeEnv_(p.tenv))
    ctx.add(T.ParamValues(nR=4, nC=4))

    # Run a representative pipeline on the rules conjunction
    root = p.rules.as_expr().node
    pm = PassManager(
        A.RolesPass(p),
        T.ParamSubPass(),
        T.ConcretizeVarsPass(),
        T.ConcretizeCollectionsPass(),
        T.ConstPropPass(),
        A.TypeInferencePass(),
        A.AstPrinterPass(),
    )
    _ = pm.run(root, ctx)
    print(ctx.get(A.PrintedAST).text)
    # If we got here, the passes cooperated on this ruleset
    assert True


