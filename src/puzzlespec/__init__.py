from .compiler.dsl import ir as _ir, ast as _ast

# Base Types
from .compiler.dsl.ast import UnitType, BoolType, IntType
Unit = UnitType(_ir.UnitT())
Bool = BoolType(_ir.BoolT())
Int = IntType(_ir.IntT())
_base_types = ['Unit', 'Bool', 'Int']

# ast constructors
from .compiler.dsl.ast import cartprod, coproduct, fin
_ast = ['cartprod', 'coproduct', 'fin']

# ND constructors
#from .compiler.dsl.nd_lib import fin, range_ as range
#_nd = ['fin', 'range']

# constructors
from .libs.std import sum, distinct, all_same, count, U, make_enum, enumT
_constructors = ['sum', 'distinct', 'all_same', 'count', 'U', 'make_enum', 'enumT']

# vars
from .libs.var_def import var, func_var
_vars = ['var', 'func_var']

# helper classes
from .compiler.dsl.spec_builder import PuzzleSpecBuilder
from .compiler.dsl.setter import VarSetter
_helpers = ['PuzzleSpecBuilder', 'VarSetter']
__all__ = [
    *_base_types,
    *_ast,
    *_constructors,
    *_vars,
    *_helpers,
]

import sys

def _puzzlespec_repr():
    return "<puzzlespec: domain-centric DSL with dependent constraints and SMT compilation>"

sys.modules[__name__].__repr__ = _puzzlespec_repr
