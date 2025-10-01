from puzzlespec import get_puzzle
from puzzlespec.compiler.dsl import ir, ir_types as irT
from puzzlespec.compiler.passes import Context, PassManager, analyses as A, transforms as T

" Test full pipeline"
def t0():
    p = get_puzzle("unruly")

    ctx = Context()
    ctx.add(A.TypeEnv_(p.tenv))
    ctx.add(T.ParamValues(nR=4, nC=4))

    # Run a representative pipeline on the rules conjunction
    root = p.rules.node
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

t0()


"test_param_constraints_fully_simplify_to_true_when_params_even"
def t1():
    spec = get_puzzle("unruly")

    root = spec.param_constraints.as_expr().node

    ctx = Context()
    # Supply environments
    ctx.add(A.TypeEnv_(spec.tenv))
    ctx.add(T.ParamValues(nR=4, nC=4))

    pm = PassManager(
        T.ParamSubPass(),
        T.ConstPropPass(),
    )
    new_root = pm.run(root, ctx)

    assert isinstance(new_root, ir.Lit)
    assert new_root.value is True
