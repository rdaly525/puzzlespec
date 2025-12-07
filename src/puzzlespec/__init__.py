from .compiler.dsl import ir as _ir, ast as _ast

# Base Types
from .compiler.dsl.ast import UnitType, BoolType, IntType, EnumType
Unit = UnitType(_ir.UnitT())
Bool = BoolType(_ir.BoolT())
Int = IntType(_ir.IntT())
_base_types = ['Unit', 'Bool', 'Int', 'EnumType']


# constructors
from .libs.std import fin, interval, sum, distinct, all_same, count, enum, U
_constructors = ['fin', 'interval', 'sum', 'distinct', 'all_same', 'count', 'enum', 'U']

# vars
from .libs.var_def import param, gen_var, decision_var, var, func_var
_vars = ['param', 'gen_var', 'decision_var', 'var', 'func_var']

# helper classes
from .compiler.dsl.spec_builder import PuzzleSpecBuilder
from .compiler.dsl.setter import VarSetter
_helpers = ['PuzzleSpecBuilder', 'VarSetter']
__all__ = [
    *_base_types,
    *_constructors,
    *_vars,
    *_helpers,
]

import sys

def _puzzlespec_repr():
    return "<puzzlespec: domain-centric DSL with dependent constraints and SMT compilation>"

sys.modules[__name__].__repr__ = _puzzlespec_repr