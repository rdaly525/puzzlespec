from __future__ import annotations
from functools import singledispatchmethod, singledispatch
from multiprocessing import Value
import typing as tp
from typing import TYPE_CHECKING
from abc import ABC, abstractmethod
import inspect

from puzzlespec.compiler.dsl.ir import _LambdaPlaceholder

if TYPE_CHECKING:
    from ..dsl import ir

class AnalysisObject(ABC): ...

class Context:
    def __init__(self):
        self._store: tp.Dict[tp.Type[AnalysisObject], AnalysisObject] = {}

    def add(self, result: object, replace=True):
        if not replace and type(result) in self._store:
            raise ValueError(f"Context already contains {type(result)}")
        self._store[type(result)] = result

    def get(self, cls: tp.Type[AnalysisObject], *args) -> AnalysisObject:
        if len(args) >1:
            raise ValueError("Only one default")
        if cls not in self._store:
            if len(args)==0:
                raise KeyError(f"Context does not contain {cls}")
            else:
                return args[0]
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
            mnames = ", ".join(str(m.__qualname__) for m in missing_deps)
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


def handles(*explicit_types: type, mark_invalid=False):
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
        if mark_invalid:
            def fn(self, node):
                raise ValueError(f"Should not be here, {node} Marked invalid")
        _PENDING.setdefault(key, []).append((fn, concrete))

        return fn
    return deco

class Analysis(Pass):
    enable_memoization=True
    
    def __call__(self, root: ir.Node, ctx: 'Context', cache = {}) -> ir.Node:
        if self.enable_memoization:
            self._cache = cache
        self.ensure_dependencies(ctx)
        # Initialize memoization for this transformation
        if self.enable_memoization:
            self._cache = {}
        aobj = self.run(root, ctx)
        if not isinstance(aobj, AnalysisObject):
            raise RuntimeError(f"Analysis pass {self.name} did not return an AnalysisObject, {aobj}")
        return aobj
 
    def visit(self, node: ir.Node) -> tp.Any:
        self.visit_children(node)

    @abstractmethod
    def run(self, root: ir.Node, ctx: 'Context'):
        raise NotImplementedError()

    def visit_children(self, node: ir.Node) -> tp.Tuple[tp.Any]:
        return tuple(self.visit(c) for c in node._children)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "__call__" in cls.__dict__:
            raise ValueError("Cannot override __call__")
        if "run" not in cls.__dict__:
            raise ValueError("Must override run")
         
        v = cls.__dict__.get("visit", None)
        if v is None:
            def v(self, node):
                return super(cls, self).visit(node)

        # Define the base dispatcher visit method
        def _base(self, node):
            return v(self, node)
        dispatcher = singledispatchmethod(_base)
        
        # Add the dispatched methods
        from ..dsl import ir
        # consume exactly the queued (fn, types) for THIS class
        key = (cls.__module__, cls.__qualname__)
        for fn, types in _PENDING.pop(key, []):
            for t in types:
                dispatcher.register(t)(fn)

        # Define custom visit function to do caching
        def visit(self, node: ir.Node):
            if self.enable_memoization:
                if node in self._cache:
                    return self._cache[node]
            # Hacked way to get the dispatcher to work without binding to an instance
            new_val = dispatcher.__get__(self, type(self))(node) 
            
            if self.enable_memoization:
                # Add new node to cache
                assert node not in self._cache
                self._cache[node] = new_val
            return new_val
        setattr(cls, "visit", visit)


class Transform(Pass):
    enable_memoization=True
    
    def __call__(self, root: ir.Node, ctx: 'Context', cache = {}) -> ir.Node:
        if self.enable_memoization:
            self._cache = cache
        self.ensure_dependencies(ctx)
        # Initialize memoization for this transformation
        if self.enable_memoization:
            self._cache = {}
            self._bframes = []
        new_root = self.run(root, ctx)
        from ..dsl import ir
        if not isinstance(new_root, ir.Node):
            raise RuntimeError("Transform pass did not return an IR node")
        return new_root

    def visit(self, node: ir.Node) -> ir.Node:
        # Fallback: recurse
        new_children = self.visit_children(node)
        result = node.replace(*new_children)
        return result

    def run(self, root: ir.Node, ctx: 'Context') -> ir.Node:
        return self.visit(root)

    def visit_children(self, node: ir.Node) -> tp.Tuple[ir.Node]:
        return tuple(self.visit(c) for c in node._children)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "__call__" in cls.__dict__:
            raise ValueError("Cannot override __call__")
         
        v = cls.__dict__.get("visit", None)
        if v is None:
            def v(self, node):
                return super(cls, self).visit(node)

        # Define the base dispatcher visit method
        def _base(self, node):
            return v(self, node)
        dispatcher = singledispatchmethod(_base)
        
        # Add the dispatched methods
        from ..dsl import ir
        # consume exactly the queued (fn, types) for THIS class
        key = (cls.__module__, cls.__qualname__)
        for fn, types in _PENDING.pop(key, []):
            for t in types:
                dispatcher.register(t)(fn)

        # Define custom visit function that creates new keys
        def visit(self, node: ir.Node):
            if self.enable_memoization:
                if isinstance(node, ir.BoundVar):
                    cache_key = (self._bframes[-(node.idx+1)], node._key)
                else:
                    cache_key = node._key
                if cache_key in self._cache:
                    return self._cache[cache_key]
                if isinstance(node, ir.Lambda):
                    self._bframes.append(node._key)
            
            # Hacked way to get the dispatcher to work without binding to an instance
            new_node = dispatcher.__get__(self, type(self))(node)
            if new_node._key == node._key:
                new_node = node
 
            if self.enable_memoization:
                if isinstance(node, ir.Lambda):
                    self._bframes.pop()
                # Add new node to cache
                assert cache_key not in self._cache
                self._cache[cache_key] = new_node
            return new_node
        setattr(cls, "visit", visit)

class PassManager:
    def __init__(self, *passes: Pass, verbose=False, max_iter=5):
        self.passes = passes
        self.verbose = verbose
        self.max_iter = max_iter

    def run(self, root: ir.Node, ctx: tp.Optional[Context] = None, fixed_point=False) -> ir.Node:
        if ctx is None:
            ctx = Context()
        if fixed_point:
            return self._run_fixed(root, self.passes, ctx)
        return self._run_passes(root, self.passes, ctx)
    
    def _run_pass(self, root: ir.Node, p: Pass, ctx: Context) -> ir.Node:
        if self.verbose:
            print(f"P: {p.__class__.__name__} on {id(root)}")
        if isinstance(p, Transform):
            root = p(root, ctx)
        else:
            assert isinstance(p, Analysis)
            anal_obj = p(root, ctx)
            ctx.add(anal_obj)
        return root
    
    def _run_passes(self, root: ir.Node, passes: tp.Iterable[Pass], ctx: Context) -> ir.Node:
        for p in passes:
            if isinstance(p, tp.Iterable):
                root = self._run_fixed(root, p, ctx)
            else:
                root = self._run_pass(root, p, ctx)
        return root

    # Does a fixed point iteration
    def _run_fixed(self, root: ir.Node, passes: tp.Iterable[Pass], ctx: 'Context') -> ir.Node:
        for _ in range(self.max_iter):
            new_root = self._run_passes(root, passes, ctx)
            print('KEYS=?', new_root._key == root._key)
            print('IDS', id(new_root), id(root))
            if new_root == root:
                return new_root
            root = new_root
        raise RuntimeError(f"Fixed point iteration did not converge in {self.max_iter} iterations")