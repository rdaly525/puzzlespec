from __future__ import annotations
import typing as tp
from . import ir, ast
from ..passes.analyses.kind_check import get_rawT

def fin(n: ast.IntOrExpr):
    n = ast.IntExpr.make(n)
    T = ir.DomT(carT=ir.IntT(), _ord=True)
    node = ir.Fin(T, n.node)
    return OrdDomainExpr(ast.DomainExpr(node))

def interval(lo: ast.IntOrExpr, hi: ast.IntOrExpr) -> ArrayExpr:
    lo = ast.IntExpr.make(lo)
    hi = ast.IntExpr.make(hi)
    #return fin(hi-lo).map(lambda i: i+lo)
    T = ir.DomT(carT=ir.IntT(), _ord=True)
    return ast.DomainExpr(ir.Range(T, lo.node, hi.node))

def range_(*args: ast.IntOrExpr) -> ast.DomainExpr:
    if len(args) == 0:
        raise ValueError("Range expects at least one argument")
    if len(args) == 1:
        return fin(args[0])
    if len(args) == 2:
        return interval(args[0], args[1])
    if len(args) == 3:
        raise NotImplementedError("Range with step is not implemented")
    raise ValueError("Range expects one to three arguments")

class OrdDomainExpr(ast.DomainExpr):
    def __init__(self, e: ast.DomainExpr):
        assert isinstance(e, ast.DomainExpr)
        _ord = e.T.node._ord
        if not isinstance(_ord, bool) or not _ord:
            raise ValueError("Not ordered")
        if not isinstance(e.T.carT, ast.IntType):
            raise NotImplementedError()
        super().__init__(e.node)
    
    def map(self, fn: tp.Callable) -> ArrayExpr:
        func = super().map(fn)
        return ArrayExpr(func)
 
    def slice(self, lo: ast.IntExpr, hi: ast.IntExpr) -> ArrayExpr:
        lo, hi = ast.IntExpr.make(lo), ast.IntExpr.make(hi)
        node = ir.Slice(self.node.T, self.node, lo.node, hi.node)
        return OrdDomainExpr(ast.DomainExpr(node))
        #return fin(hi-lo).map(lambda i: i+lo)

    def elemAt(self, idx: ast.IntOrExpr) -> ast.FuncExpr:
        idx = ast.IntExpr.make(idx)
        elem = ast.IntExpr(ir.ElemAt(ir.IntT(), self.node, idx.node))
        return elem
        #node = ir.Singleton(ir.DomT(ir.IntT()), elem.node)
        #singleton_dom = ast.DomainExpr(node)
        #return singleton_dom
    
    def windows(self, size: ast.IntOrExpr, stride: ast.IntOrExpr=1) -> ArrayExpr:
        size = ast.IntExpr.make(size)
        stride = ast.IntExpr.make(stride)
        dom = fin((self.size-(size-stride))//stride)
        wins = dom.map(
            lambda i: self[i*stride:i*stride+size] 
        )
        assert wins is not None
        return wins

    def map(self, fn: tp.Callable) -> ArrayExpr:
        func = super().map(fn)
        return ArrayExpr(func)
    
    def __getitem__(self, idx: tp.Any) -> ast.FuncExpr:
        if isinstance(idx, slice):
            start, step, stop = idx.start, idx.step, idx.stop
            if step is not None:
                raise ValueError("No step allowed in slices")
            if start is None and stop is None:
                return self
            if start is None:
                start = 0
            if stop is None:
                stop = self.size
            return self.slice(start, stop)
        elif isinstance(idx, (int, ast.IntExpr)):
            idx = ast.IntExpr.make(idx)
            return self.elemAt(idx)
        elif isinstance(idx, ast.DomainExpr):
            return self.gather(idx)

    def __mul__(self, other: ast.DomainExpr):
        return nd_cartprod(self, other)

def _get_axes(dom: ast.DomainExpr):
    # Calculate axes
    rawT = get_rawT(dom.T.node)
    assert isinstance(rawT, ir.DomT)
    assert isinstance(rawT._ord, tuple)
    assert isinstance(rawT._elemAt, tuple)
    assert len(rawT._ord) == len(rawT._elemAt)
    assert len(rawT._ord) == len(dom.T.carT)
    axes = tuple(not elemAt for elemAt in rawT._elemAt)
    ords = tuple(ord for ord in rawT._ord)
    return axes, ords

# Represents Fin x Dom x Fin x Fin x ...
class NDSeqDomainExpr(ast.DomainExpr):
    def __init__(self, dom: ast.DomainExpr):
        assert isinstance(dom, ast.DomainExpr)
        if isinstance(dom.T, ast.ImageType):
            raise NotImplementedError("ImageType not implemented")
        assert isinstance(dom.T, ast.DomainType)
        if not isinstance(dom.T.carT, ast.TupleType):
            raise ValueError(f"Expected tuple carT, got {dom.T.carT}")
        self.num_factors = len(dom.T.carT)
        axes, ords = _get_axes(dom)
        assert len(axes) == self.num_factors
        assert len(ords) == self.num_factors
        doms = [dom.dom_proj(i) for i in range(self.num_factors)]
        dom_prod = ast.cartprod(*doms)
        doms = [OrdDomainExpr(dom) if ord else dom for dom, ord in zip(doms, ords)]
        self.axes = axes
        self.doms = doms
        super().__init__(dom_prod.node)

    @property
    def rank(self):
        return sum(self.axes)

    @property
    def axes_doms(self) -> tp.Tuple[OrdDomainExpr]:
        return tuple(dom for  i, dom in enumerate(self.doms) if self.axes[i])

    def windows(self, size: ast.IntOrExpr, stride: ast.IntOrExpr=1) -> NDArrayExpr:
        if self.rank != 1:
            raise ValueError("Must be rank 1 for windows")
        return self.tiles((size,), (stride,))

    def tiles(self, size: tp.Tuple[ast.IntOrExpr, ...], stride: tp.Tuple[ast.IntOrExpr, ...]=None) -> NDArrayExpr:
        rank = self.rank
        if stride == None:
            strides = [1 for _ in range(rank)]
        strides = [ast.IntExpr.make(s) for s in stride]
        sizes = [ast.IntExpr.make(s) for s in size]
        if len(sizes) != rank or len(strides) != rank:
            raise ValueError(f"Expected size and stride for all dimensions ({rank}), got {size} and {stride}")
        #wins = [dom.windows(size, stride) for size, stride, dom in zip(sizes, strides, self.axes_doms)]
        # win is Fin -> (Fin -> Int)
        funcs = []
        def e_to_id(e: ast.Expr, domT: ast._DomainType):
            singleton = ast.DomainExpr(ir.Singleton(domT.node, e.node))
            return singleton

        offset=0
        for axis, dom in zip(self.axes, self.doms):
            if axis:
                func = dom.windows(sizes[offset], strides[offset])
                offset+=1
            else:
                func = dom.map(lambda e: e_to_id(e, dom.T))
                #func = dom
            funcs.append(func)
        return nd_cartprod(*funcs)
    
    # Fin(3) x Fin(2)
    # 00 01 02
    # 10 11 12
    # f(rc -> r+c)
    def map(self, fn: tp.Callable) -> NDArrayExpr:
        func = super().map(fn)
        return NDArrayExpr(func)

    # Fin(nR) -> (ND({r} -> r, Fin(nC)-> Int)
    def rows(self) -> ArrayExpr:
        if self.rank != 2:
            raise ValueError(f"Expected 2D array, got {self.T}")
        rows = self.axes_doms[0].map(lambda r: self[r,:])
        return rows

    def cols(self) -> ArrayExpr:
        if self.rank != 2:
            raise ValueError(f"Expected 2D array, got {self.T}")
        return self.axes_doms[1].map(lambda c: self[:,c])

    def __getitem__(self, val: tp.Any) -> NDArrayExpr:
        if not isinstance(val, tuple) and len(val) != self.rank:
            raise ValueError(f"Getitem must have length {self.rank}")
        funcs: tp.List[ast.FuncExpr] = []
        offset=0
        for axis, dom in zip(self.axes, self.doms):
            if axis:
                v = val[offset]
                func = dom[v]
                offset +=1
            else:
                func = dom
            funcs.append(func)
        return nd_cartprod(*funcs)

    def __mul__(self, other: ast.DomainExpr):
        return nd_cartprod(self, other)

# Array Literal
def array(vals: tp.List[tp.Any]) -> ArrayExpr:
    vals = [ast.Expr.make(v) for v in vals]
    raise NotImplementedError("Array literal not implemented")

class ArrayExpr(ast.FuncExpr):
    def __init__(self, e: ast.FuncExpr):
        if e.domain.T._ord is not True:
            raise ValueError("Array's must have ord domains")
        super().__init__(e.node)

    @property
    def domain(self) -> OrdDomainExpr:
        return OrdDomainExpr(super().domain)

    def windows(self, size: ast.IntOrExpr, stride: ast.IntOrExpr=1) -> ArrayExpr:
        wins = self.domain.windows(size, stride) # Array[Array]
        return wins.map(lambda win: win.map(lambda i: self[i]))

    def __getitem__(self, k: tp.Any):
        if isinstance(k, (int, ast.IntExpr)):
            k = ast.IntExpr.make(k)
            return self.apply(self.domain.elemAt(k))
        elif isinstance(k, slice):
            return wrap_nd(self[self.domain[k]])
        elif isinstance(k, ast.DomainExpr):
            return wrap_nd(super().gather(k))
        raise NotImplementedError(f"Cannot handle {type(k)} in __getitem__")

    def apply(self, i: ast.IntExpr):
        return wrap_nd(super().apply(i))

    def __iter__(self) -> None:
        raise ValueError("ArrayExpr is not iterable at python runtime")

def wrap_nd(e: ast.Expr):
    if isinstance(e, ast.DomainExpr):
        if isinstance(e.T, ast.ImageType):
            return e
        elif isinstance(e.T.carT, ast.TupleType):
            return NDSeqDomainExpr(e)
        else:
            rawT = get_rawT(e.T.node)
            assert isinstance(rawT._ord, bool)
            if rawT._ord:
                return OrdDomainExpr(e)
            return e
    elif isinstance(e, ast.FuncExpr):
        domT = e.domain.T
        if isinstance(domT, ast.ImageType):
            return e
        elif isinstance(domT.carT, ast.TupleType):
            return NDArrayExpr(e)
        else:
            rawT = get_rawT(domT.node)
            assert isinstance(rawT._ord, bool)
            if rawT._ord:
                return ArrayExpr(e)
            return e
    else:
        return e

# Func[NDDom -> T]
class NDArrayExpr(ast.FuncExpr):
    def __init__(self, func: ast.FuncExpr):
        super().__init__(func.node)
        dom = super().domain
        assert isinstance(dom.T.carT, ast.TupleType)
        self.num_factors = len(dom.T.carT)
        self._dom = dom
    
    @property
    def axes(self):
        return self.domain.axes

    @property
    def domain(self) -> NDSeqDomainExpr:
        return NDSeqDomainExpr(super().domain)

    def map(self, fn: tp.Callable) -> NDSeqDomainExpr:
        return NDArrayExpr(self.domain.map(lambda elem: fn(self.apply(elem))))

    def apply(self, i: ast.Expr):
        return wrap_nd(super().apply(i))

    def rows(self) -> ArrayExpr:
        return self.domain.rows().map(lambda row_dom: self[row_dom])

    def cols(self) -> ArrayExpr:
        return self.domain.cols().map(lambda col_dom: self[col_dom])

    def windows(self, size: ast.IntOrExpr, stride: ast.IntOrExpr=1):
        wins = self.tiles((size,), (stride,))
        assert wins is not None
        return wins

    def tiles(self, size: tp.Tuple[ast.IntOrExpr, ...], stride: tp.Tuple[ast.IntOrExpr, ...]=None) -> NDArrayExpr:
        dom_tiles = self.domain.tiles(size, stride)
        def tlam(dom):
            return self[dom]
        return dom_tiles.map(
            #lambda tile_dom: self[tile_dom]
            tlam
        )

    def __getitem__(self, dom: ast.DomainExpr) -> ast.FuncExpr:
        return wrap_nd(super().__getitem__(dom))


def lift_to_dom(val: ast.Expr) -> ast.DomainExpr:
    domT = ir.DomT(carT=val.T.node, _elemAt=True)
    return ast.DomainExpr(ir.Singleton(domT, val.node))
def lift_to_func(val: ast.Expr) -> ast.FuncExpr:
    return lift_to_dom(val).identity

def nd_cartprod(*dfs: tp.Union[ast.DomainExpr, ast.FuncExpr]) -> tp.Union[ast.TupleExpr, NDSeqDomainExpr, NDArrayExpr]:
    if all(isinstance(df, ast.DomainExpr) for df in dfs):
        return NDSeqDomainExpr(ast.cartprod(*dfs))
    if any(isinstance(df, ast.FuncExpr) for df in dfs):
        funcs: tp.List[ast.FuncExpr] = []
        for df in dfs:
            if isinstance(df, ast.FuncExpr):
                #if not isinstance(df, ArrayExpr):
                #    raise ValueError
                funcs.append(df)
            elif isinstance(df, ast.DomainExpr):
                return df.identity
                #raise NotImplementedError("Cannot handle DomainExpr in nd_cartprod")
            else:
                funcs.append(lift_to_func(df))
        dom_prod = nd_cartprod(*(func.domain for func in funcs))
        return dom_prod.map(lambda indices: nd_cartprod(*(func.apply(indices[i]) for i, func in enumerate(funcs))))
    if any(isinstance(df, ast.DomainExpr) for df in dfs):
        doms = []
        for df in dfs:
            if isinstance(df, ast.DomainExpr):
                doms.append(df)
            else:
                doms.append(lift_to_dom(df))
        return NDSeqDomainExpr(ast.cartprod(*doms))
    return ast.TupleExpr.make(dfs)