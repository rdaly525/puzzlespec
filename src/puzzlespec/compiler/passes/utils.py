from ..dsl import PuzzleSpec
from .analyses import TypeEnv_
from .transforms import ParamSubPass, ParamValues
from .pass_base import Context, PassManager

def concretize_params(spec: PuzzleSpec, **kwargs):
    ctx = Context()
    ctx.add(TypeEnv_(spec.tenv))
    ctx.add(ParamValues(**kwargs))

    
    pm = PassManager(
        ParamSubPass(),
    )
    return pm.run(spec.param_constraints.as_expr().node, ctx)


