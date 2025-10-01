from __future__ import annotations
from functools import singledispatchmethod
import typing as tp
from typing import TYPE_CHECKING
from abc import ABC, abstractmethod
import inspect

if TYPE_CHECKING:
    from ..dsl import ir

class AnalysisObject(ABC): ...

class Context:
    def __init__(self):
        self._store: tp.Dict[tp.Type[AnalysisObject], AnalysisObject] = {}

    def add(self, result: object):
        self._store[type(result)] = result

    def get(self, cls: tp.Type[AnalysisObject]) -> AnalysisObject:
        if cls not in self._store:
            raise KeyError(f"Context does not contain {cls}")
        return self._store[cls]
    
    def try_get(self, cls: tp.Type[AnalysisObject]) -> tp.Optional[AnalysisObject]:
        if cls not in self._store:
            return None
        return self._store[cls]
    
class Pass(ABC):
    name: str
    requires: tp.Tuple[tp.Type[AnalysisObject], ...] = ()
    produces: tp.Tuple[tp.Type[AnalysisObject], ...] = ()

    def ensure_dependencies(self, ctx: 'Context'):
        requires = self.requires if isinstance(self.requires, tuple) else (self.requires,)
        for r in requires:
            if not issubclass(r, AnalysisObject):
                raise TypeError(f"Pass {self.name} requires {r} which is not a subclass of AnalysisObject")
        missing_deps = [r for r in requires if ctx.try_get(r) is None]
        if missing_deps != []:
            raise RuntimeError(f"Pass {self.name} requires {missing_deps}")

    @abstractmethod
    def __call__(self, root: ir.Node, ctx) -> ir.Node: ...

_PENDING: dict[tuple[str, str], list[tuple[tp.Callable, tuple[type, ...]]]] = {}

def _second_param_name(fn: tp.Callable) -> str:
    it = iter(inspect.signature(fn).parameters.values())
    next(it, None)
    p2 = next(it, None)
    if p2 is None:
        raise TypeError(f"{fn.__qualname__} must have (self, node)")
    return p2.name

def _explode_types(t: tp.Any) -> tp.Tuple[type, ...]:
    origin = tp.get_origin(t)
    if origin is tp.Annotated:
        t = tp.get_args(t)[0]
        origin = tp.get_origin(t)
    if origin is tp.Union:
        return tuple(tt for tt in tp.get_args(t) if tt is not type(None))
    return (t,)

def handles(*explicit_types: type):
    """
    @handles()                  -> infer from 2nd param annotation
    @handles(A, B)              -> explicit types
    (stackable; multiple '_' defs are fine)
    """
    def deco(fn: tp.Callable) -> tp.Callable:
        # resolve types
        if explicit_types:
            types = explicit_types
        else:
            try:
                hints = tp.get_type_hints(fn, globalns=getattr(fn, "__globals__", None))
            except Exception:
                hints = getattr(fn, "__annotations__", {})
            pname = _second_param_name(fn)
            ann = hints.get(pname) or getattr(fn, "__annotations__", {}).get(pname)
            if ann is None:
                raise TypeError(f"@handles couldn't infer types for {fn.__qualname__}; annotate the 2nd param")
            types = _explode_types(ann)

        # filter & validate
        concrete = tuple(t for t in types if isinstance(t, type) and t is not type(None))  # noqa: E721
        if not concrete:
            raise TypeError(f"@handles on {fn.__qualname__} resolved no concrete types")
        
        # queue this exact (function, types) pair so same-named defs aren’t lost
        cls_qual = fn.__qualname__.rsplit(".", 1)[0]  # e.g., "Getter"
        key = (fn.__module__, cls_qual)
        _PENDING.setdefault(key, []).append((fn, concrete))

        return fn
    return deco

class Analysis(Pass):
    def __call__(self, root: ir.Node, ctx: 'Context') -> ir.Node:
        self.ensure_dependencies(ctx)
        res = self.run(root, ctx)
        ctx.add(res)
        return root
    
    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)

        # build or wrap a per-class dispatcher
        v = cls.__dict__.get("visit")
        if isinstance(v, singledispatchmethod):
            dispatcher = v
        else:
            if callable(v):
                def _default(self, node, _plain=v):
                    return _plain(self, node)
            else:
                def _default(self, node):
                    return super(cls, self).visit(node)
            dispatcher = singledispatchmethod(_default)
            setattr(cls, "visit", dispatcher)

        # consume exactly the queued (fn, types) for THIS class
        key = (cls.__module__, cls.__qualname__)
        for fn, types in _PENDING.pop(key, []):
            for t in types:
                dispatcher.register(t)(fn)

        # (optional) also register uniquely named methods still in __dict__
        # in case someone didn’t use @handles but set __handles__ themselves
        for obj in cls.__dict__.values():
            types = getattr(obj, "__handles__", ())
            for t in types:
                dispatcher.register(t)(obj)

    def visit(self, node: ir.Node):
        # Fallback: recurse
        for child in node._children:
            self.visit(child)
        return node

    @abstractmethod
    def run(self, root: ir.Node, ctx: 'Context') -> AnalysisObject: ...

class Transform(Pass):
    
    def visit(self, node: ir.Node) -> ir.Node:
        # Check if we've already transformed this node
        if node in self._transform_memo:
            return self._transform_memo[node]
        
        # Fallback: recurse
        new_children = tuple(self.visit(c) for c in node._children)
        result = node if new_children == node._children else node.replace(*new_children)
        
        # Memoize the result
        self._transform_memo[node] = result
        return result

    def run(self, root: ir.Node, ctx: 'Context') -> ir.Node:
        # Default implementation: just visit the root
        return self.visit(root)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # Determine the subclass's dispatcher:
        # - If subclass already defined a singledispatchmethod visit, use it.
        # - If subclass defined a plain visit, wrap *that* as the default.
        # - Otherwise, synthesize a dispatcher whose default delegates to super().visit.
        v = cls.__dict__.get("visit")
        if isinstance(v, singledispatchmethod):
            dispatcher = v
        else:
            if callable(v):
                # subclass provided a plain visit; make it the default
                def _default(self, node, _plain=v):
                    return _plain(self, node)
            else:
                # no visit defined on subclass; delegate to base fallback
                def _default(self, node):
                    return super(cls, self).visit(node)
            dispatcher = singledispatchmethod(_default)
            setattr(cls, "visit", dispatcher)

        # consume exactly the queued (fn, types) for THIS class
        key = (cls.__module__, cls.__qualname__)
        for fn, types in _PENDING.pop(key, []):
            for t in types:
                dispatcher.register(t)(fn)

        # (optional) also register uniquely named methods still in __dict__
        # in case someone didn't use @handles but set __handles__ themselves
        for obj in cls.__dict__.values():
            for t in getattr(obj, "__handles__", ()):
                dispatcher.register(t)(obj)

    # Shared helper for boolean negation used by some Transform implementations
    #def _make_not(self, n: Node) -> Node:
    #    from ..dsl import ir as _ir  # local import to avoid cycles
    #    if isinstance(n, _ir.Lit):
    #        return _ir.Lit(not n.value)
    #    return _ir.Not(n)

    def __call__(self, root: ir.Node, ctx: 'Context') -> ir.Node:
        self.ensure_dependencies(ctx)
        # Initialize memoization for this transformation
        self._transform_memo = {}
        return self.run(root, ctx)

class PassManager:
    def __init__(self, *passes: Pass):
        self.passes = passes
    
    def run(self, root: ir.Node, ctx: tp.Optional[Context] = None) -> ir.Node:
        if ctx is None:
            ctx = Context()
        for p in self.passes:
            new_root = p(root, ctx)
            root = new_root
        return root