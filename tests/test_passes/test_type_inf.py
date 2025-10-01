from puzzlespec import get_puzzle
from puzzlespec.compiler.dsl import ir_types as irT
from puzzlespec.compiler.passes import analyses as A, transforms as T
from puzzlespec.compiler.passes import Context, PassManager
from puzzlespec.compiler.dsl import ir


"test_type_inference_on_param_constraints_is_bool"
def t0():
    spec = get_puzzle("unruly")

    # Param constraints
    root = spec.param_constraints.node
    ctx = Context()
    # Supply environments
    ctx.add(A.TypeEnv_(spec.tenv))

    pm = PassManager(
        A.TypeInferencePass(),
        A.AstPrinterPass(),
    )
    pm.run(root, ctx)
    assert ctx.get(A.TypeValues).mapping[root] == irT.Bool
    print(ctx.get(A.PrintedAST).text)

    # Rules
    root = spec.rules.node
    pm.run(root, ctx)
    assert ctx.get(A.TypeValues).mapping[root] == irT.Bool
    print(ctx.get(A.PrintedAST).text)

t0()