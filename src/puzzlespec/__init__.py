from .compiler.dsl import ast
from .compiler.dsl import spec
from .compiler.dsl import ir_types
from .puzzles import get_puzzle

import typing as tp

PuzzleSpec = spec.PuzzleSpec
Int = ir_types.Int
Bool = ir_types.Bool