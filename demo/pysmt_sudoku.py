from pysmt.shortcuts import *
import math

# NxN board
def sudoku(N: int):

    # Verify parameter is square
    assert math.isqrt(N)**2 == N

    # Variable declaration: cell_vals[r][c] is the value in row r, column c
    cell_vals = [[Symbol(f"x{r}{c}", INT) for c in range(N)] for r in range(N)]
    
    constraints = []
    # Constrain the domain of cell_vals: 1 <= x[r][c] <= 9
    for r in range(N):
        for c in range(N):
            v = cell_vals[r][c]
            constraints.append(GE(v, Int(1)))
            constraints.append(LE(v, Int(9)))
    
    # Box constraints: each box has distinct values
    box_size = math.isqrt(N)
    for br in range(0, N, box_size):
        for bc in range(0, N, box_size):
            box_cells = []
            for dr in range(box_size):
                for dc in range(box_size):
                    r = br + dr
                    c = bc + dc
                    box_cells.append(cell_vals[r][c])
            constraints.append(Distinct(box_cells))


    # Row constraints: each row has distinct values
    for r in range(N):
        row_cells = [cell_vals[r][c] for c in range(N)]
        constraints.append(Distinct(row_cells))
    # Col constraints: each col has distinct values

    # Box constraints: each 3x3 box has distinct values
   
    # Column constraints: each column has distinct values
    for c in range(N):
        col_cells = [cell_vals[r][c] for r in range(N)]
        constraints.append(Distinct(row_cells))
    
    givens = {
        (0, 0): 5,
        (0, 1): 3,
        (1, 0): 6,
        (4, 4): 7,
        (7, 8): 9,
    }

    for (r, c), val in givens.items():
        constraints.append(Equals(cell_vals[r][c], Int(val)))