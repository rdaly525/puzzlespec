from puzzlespec import get_puzzle, PuzzleSpec
from puzzlespec.compiler.dsl import ir_types as irT
from puzzlespec.compiler.passes import analyses as A, transforms as T
from puzzlespec.compiler.passes import Context, PassManager
from puzzlespec.compiler.dsl import ir


# Gets a new instance of the puzzle Unruly
spec = get_puzzle('unruly')

# set the parameters.
spec.set_params(N=8)

# Resolve all index types (i.e., cellIndexT)

# Set all the generator parameters (i.e., the clues)
given_mask = spec.get_var('given_mask')
given_vals = spec.get_var('given_vals')

# Add particular clues
"""
1..1..1.
.1.....1
.10.0.0.
........
...1.0..
1..1.00.
........
.1...0.1
"""