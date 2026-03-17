"""Shared fixtures and helpers for pass tests."""
import pytest
from puzzlespec import Int, Bool, var, param, func_var
from puzzlespec.compiler.dsl import ir, ast
from puzzlespec.compiler.dsl.ast import IntExpr, BoolExpr, DomainExpr, FuncExpr
from puzzlespec.compiler.passes.pass_base import Context
from puzzlespec.libs import std


def run_transform(cls, node, **kwargs):
    """Run a Transform subclass through __call__ and return the result node."""
    p = cls(**kwargs) if kwargs else cls()
    result, _ = p(node, Context())
    return result


def run_analysis(cls, node, ctx=None):
    """Run an Analysis subclass through __call__ and return the AnalysisObject."""
    p = cls()
    if ctx is None:
        ctx = Context()
    return p(node, ctx)
