from puzzlespec.compiler.dsl.spec_builder import PuzzleSpecBuilder
from .unruly import build_unruly_spec
from .sudoku import build_sudoku_spec
import sys
from ..compiler.dsl.spec import PuzzleSpec

def get_puzzle(name: str) -> PuzzleSpec:
    build_name = f"build_{name}_spec"
    if not hasattr(sys.modules[__name__], build_name):
        raise ValueError(f"Puzzle {name} not found")
    spec: PuzzleSpec = getattr(sys.modules[__name__], build_name)()
    return spec


