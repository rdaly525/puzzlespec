from packages.tactics import tactic, values
from packages.tactics import dom, size, contains, the_one, count_has
from packages.tactics import assign, remove
from packages.tactics import rows_from, cols_from, rows_except, foreach
from puzzlespec import Grid
from puzzlespec.puzzles.sudoku import build_sudoku_spec

# Assumed spec-DSL structure helpers (existing or to be provided by your puzzle facade):
# - rows()         -> ListExpr[IntExpr]          # all row ids
# - cols()         -> ListExpr[IntExpr]          # all column ids
# - row_cells(r)   -> ListExpr[Expr]             # cells in row r (ordered by col)
# - col_cells(c)   -> ListExpr[Expr]             # cells in column c (ordered by row)
# - cell(r, c)     -> Expr                       # the cell at row r, col c


from puzzlespec.ast import BoolExpr

def iff(p: BoolExpr, q: BoolExpr) -> BoolExpr:
    return (BoolExpr.make(p).implies(q)) & (BoolExpr.make(q).implies(p))

def test_xwing_row_based():
    # Build Sudoku spec and reference its decision dict directly
    spec = build_sudoku_spec()
    grid = spec.topo  # Grid2D
    # Use the public Grid API rather than index_grid here
    rows = rows_from(grid)  # list of rows of cell indices
    cols = cols_from(grid)
    # Decision variable dictionary from spec: cell_vals: {CellIdx: Int}
    [cell_vals] = spec.get_var_dicts(role="decision")

    with tactic("XWing_RowBased", explain="Row-based X-Wing eliminates v from same columns in other rows") as t:
        # Bind structure
        r1 = t.bind(rows)
        r2 = t.bind(rows)
        t.where(r1 != r2)

        cA = t.bind(cols)
        cB = t.bind(cols)
        t.where(cA != cB)

        v  = t.bind(values(1,2,3,4,5,6,7,8,9))

        R1 = r1
        R2 = r2
        # Map row cell indices to their decision variables
        R1V = R1.map(lambda idx: cell_vals[idx])
        R2V = R2.map(lambda idx: cell_vals[idx])

        # Use spec grid indexing via rows/cols
        # Intersections via structural binding: pick a cell from the row and the column and equate
        # Concrete cells are the intersection indices; reference concrete decision variables
        x1A_idx = t.bind(R1)
        y1A_idx = t.bind(cA)
        t.where(x1A_idx == y1A_idx)
        x1A = cell_vals[x1A_idx]

        x1B_idx = t.bind(R1)
        y1B_idx = t.bind(cB)
        t.where(x1B_idx == y1B_idx)
        x1B = cell_vals[x1B_idx]

        x2A_idx = t.bind(R2)
        y2A_idx = t.bind(cA)
        t.where(x2A_idx == y2A_idx)
        x2A = cell_vals[x2A_idx]

        x2B_idx = t.bind(R2)
        y2B_idx = t.bind(cB)
        t.where(x2B_idx == y2B_idx)
        x2B = cell_vals[x2B_idx]

        # Guards: in each of rows r1 and r2, v appears as a candidate in exactly the two columns cA and cB
        # 1) Exactly two candidates in r1 at columns cA, cB
        t.when(count_has(R1V, values(v)) == 2)
        t.when(contains(x1A.dom(), v) & contains(x1B.dom(), v))
        t.when(R1V.forall(lambda z: iff(contains(z.dom(), v), (z == x1A) | (z == x1B))))

        # 2) Exactly two candidates in r2 at the same columns cA, cB
        t.when(count_has(R2V, values(v)) == 2)
        t.when(contains(x2A.dom(), v) & contains(x2B.dom(), v))
        t.when(R2V.forall(lambda z: iff(contains(z.dom(), v), (z == x2A) | (z == x2B))))

        # Action: eliminate v from the same columns in all other rows
        # For each other row r3 != r1, r2, remove v from cells (r3, cA) and (r3, cB)
        # Foreach sugar; if you don't have it yet, emit two removes parametrically.
        # Here we show the intent for clarity:
        # Eliminate from column cells except the two in the wings
        from puzzlespec.ast import BoolExpr
        maskA = cA.map(lambda q: BoolExpr.make((q == x1A_idx)) | BoolExpr.make((q == x2A_idx)))
        maskB = cB.map(lambda q: BoolExpr.make((q == x1B_idx)) | BoolExpr.make((q == x2B_idx)))
        colA_others = cA.mask(BoolExpr.make(~maskA.forall(lambda b: ~b)))
        colB_others = cB.mask(BoolExpr.make(~maskB.forall(lambda b: ~b)))
        t.do(foreach(colA_others, lambda q_idx: remove(cell_vals[q_idx], values(v))))
        t.do(foreach(colB_others, lambda q_idx: remove(cell_vals[q_idx], values(v))))

        xwing_row = t.build()


def test_xwing_row_based_indices():
    # Build Sudoku spec and reference its decision dict directly
    spec = build_sudoku_spec()
    grid = spec.topo  # Grid2D
    rows = rows_from(grid)
    cols = cols_from(grid)
    [cell_vals] = spec.get_var_dicts(role="decision")

    with tactic("XWing_RowBased_Idx", explain="Row-based X-Wing via row/col indices") as t:
        # Index domains
        ri_dom = values(0,1,2,3,4,5,6,7,8)
        ci_dom = values(0,1,2,3,4,5,6,7,8)

        ri1 = t.bind(ri_dom)
        ri2 = t.bind(ri_dom)
        t.where(ri1 != ri2)

        cA = t.bind(ci_dom)
        cB = t.bind(ci_dom)
        t.where(cA != cB)

        v  = t.bind(values(1,2,3,4,5,6,7,8,9))

        # Rows and columns as lists of cell indices
        R1 = rows[ri1]
        R2 = rows[ri2]
        C_A = cols[cA]
        C_B = cols[cB]

        # Intersection indices and concrete decision vars
        x1A_idx = R1[cA]
        x1B_idx = R1[cB]
        x2A_idx = R2[cA]
        x2B_idx = R2[cB]

        x1A = cell_vals[x1A_idx]
        x1B = cell_vals[x1B_idx]
        x2A = cell_vals[x2A_idx]
        x2B = cell_vals[x2B_idx]

        # Guard: exactly two v-candidates in each row at these columns
        R1V = R1.map(lambda idx: cell_vals[idx])
        R2V = R2.map(lambda idx: cell_vals[idx])

        t.when(count_has(R1V, values(v)) == 2)
        t.when(contains(x1A.dom(), v) & contains(x1B.dom(), v))
        t.when(R1V.forall(lambda z: iff(contains(z.dom(), v), (z == x1A) | (z == x1B))))

        t.when(count_has(R2V, values(v)) == 2)
        t.when(contains(x2A.dom(), v) & contains(x2B.dom(), v))
        t.when(R2V.forall(lambda z: iff(contains(z.dom(), v), (z == x2A) | (z == x2B))))

        # Eliminate from the same columns, other rows
        from puzzlespec.ast import BoolExpr
        maskA = C_A.map(lambda q: BoolExpr.make((q == x1A_idx)) | BoolExpr.make((q == x2A_idx)))
        maskB = C_B.map(lambda q: BoolExpr.make((q == x1B_idx)) | BoolExpr.make((q == x2B_idx)))
        C_A_others = C_A.mask(BoolExpr.make(~maskA.forall(lambda b: ~b)))
        C_B_others = C_B.mask(BoolExpr.make(~maskB.forall(lambda b: ~b)))
        t.do(foreach(C_A_others, lambda q_idx: remove(cell_vals[q_idx], values(v))))
        t.do(foreach(C_B_others, lambda q_idx: remove(cell_vals[q_idx], values(v))))

        xwing_row_idx = t.build()