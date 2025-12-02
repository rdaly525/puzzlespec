import puzzlespec as ps
from puzzlespec.puzzles import get_puzzle
from puzzlespec.libs import optional as opt
from puzzlespec.backends import SMTBackend
import typing as tp
Sudoku = get_puzzle("sudoku")

print(Sudoku.pretty())