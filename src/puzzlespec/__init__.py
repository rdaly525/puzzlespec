from .compiler.dsl import ast, topology
from .compiler.dsl import spec
from .compiler.dsl import ir_types
from .puzzles import get_puzzle

import typing as tp

PuzzleSpec = spec.PuzzleSpec
Int = ir_types.Int
Bool = ir_types.Bool

def Grid(nR: ast.IntOrExpr, nC: ast.IntOrExpr) -> topology.Grid2D:
    return topology.Grid2D(nR, nC)

# Re-export selected AST constructors commonly used by specs
IntParam = ast.IntParam

