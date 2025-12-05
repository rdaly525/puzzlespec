from .compiler.dsl import ir as _ir, ast as _ast

# Base Types
from .compiler.dsl.ast import UnitType, BoolType, IntType
Unit = UnitType(_ir.UnitT())
Bool = BoolType(_ir.BoolT())
Int = IntType(_ir.IntT())
_base_types = ['Unit', 'Bool', 'Int']

# Other Types
#from .compiler.dsl.ast import TupleType, SumType, LambdaType, DomainType, FuncType
#_other_types = ['TupleType', 'SumType', 'LambdaType', 'DomainType', 'FuncType']

# ast constructors
from .compiler.dsl.ast import cartprod, coproduct
_ast = ['cartprod', 'coproduct']

# ND constructors
from .compiler.dsl.ast_nd import fin, interval, nd_cartprod
_nd = ['fin', 'interval', 'nd_cartprod']


# constructors
from .libs.std import  sum, distinct, all_same, count, make_enum, enumT
_constructors = ['sum', 'distinct', 'all_same', 'count', 'make_enum', 'enumT']

# vars
from .libs.var_def import param, gen_var, decision_var, var, func_var
_vars = ['param', 'gen_var', 'decision_var', 'var', 'func_var']

# helper classes
from .compiler.dsl.spec_builder import PuzzleSpecBuilder
from .compiler.dsl.setter import VarSetter
_helpers = ['PuzzleSpecBuilder', 'VarSetter']
__all__ = [
    *_base_types,
    *_ast,
    *_nd,
    *_constructors,
    *_vars,
    *_helpers,
]