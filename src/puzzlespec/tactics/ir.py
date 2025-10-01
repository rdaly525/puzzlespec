from __future__ import annotations
import typing as tp

# Tactic IR nodes built on the shared base IR Node class.
# This file intentionally defines only structure; no evaluation/lowering.

from puzzlespec import ir


class TacProgram(ir.Node):
    """A collection of tactic rules.

    Children: [rule_0, rule_1, ..., rule_n]
    """

    def __init__(self, *rules: ir.Node):
        super().__init__(*rules)


class TacRule(ir.Node):
    """A single tactic rule: params, guard, and actions.

    Children (fixed order):
      - params: TacParams
      - guard: ir.Node (Bool-typed expression)
      - actions: TacActions

    Fields:
      - name: str
      - explain: tp.Optional[str]
    """

    _fields = ("name", "explain")

    def __init__(self, params: ir.Node, guard: ir.Node, actions: ir.Node, *, name: str, explain: tp.Optional[str] = None):
        self.name = name
        self.explain = explain
        super().__init__(params, guard, actions)


class TacParams(ir.Node):
    """Container for rule parameters (each typically an ir.Param wrapped in a typed Expr).

    Children: [param_0, ..., param_n]
    """

    def __init__(self, *params: ir.Node):
        super().__init__(*params)


class TacActions(ir.Node):
    """Container for a sequence of actions.

    Children: [action_0, ..., action_n]
    """

    def __init__(self, *actions: ir.Node):
        super().__init__(*actions)


# --- Domain actions ---

class TacAssign(ir.Node):
    """Assign a value to a variable domain.

    Children:
      - target: ir.Node (e.g., cell variable)
      - value: ir.Node (e.g., Int literal/expression)
    """

    def __init__(self, target: ir.Node, value: ir.Node):
        super().__init__(target, value)


class TacRemove(ir.Node):
    """Remove a set of values from a variable domain.

    Children:
      - target: ir.Node
      - values: ir.Node (list/set expression)
    """

    def __init__(self, target: ir.Node, values: ir.Node):
        super().__init__(target, values)


# Canonical primary-view actions (aliases for clarity)
class TacPlace(ir.Node):
    """Place a definitive value into the primary variable view (assign)."""
    def __init__(self, var: ir.Node, value: ir.Node):
        super().__init__(var, value)


class TacForbid(ir.Node):
    """Forbid a set of values from the primary variable view's domain (remove)."""
    def __init__(self, var: ir.Node, values: ir.Node):
        super().__init__(var, values)


# --- Aggregate actions ---

class TacTightenSum(ir.Node):
    """Tighten bounds on a sum aggregate: L' <= sum(domain) <= U'.

    Children:
      - domain: ir.Node (list expression of Int)
      - lower: ir.Node (Int)
      - upper: ir.Node (Int)
    """

    def __init__(self, domain: ir.Node, lower: ir.Node, upper: ir.Node):
        super().__init__(domain, lower, upper)


class TacTightenCount(ir.Node):
    """Tighten bounds on a count aggregate for a set of values.

    Children:
      - domain: ir.Node (collection of variables/cells)
      - values: ir.Node (collection of candidate values being counted)
      - lower: ir.Node (Int)
      - upper: ir.Node (Int)
    """

    def __init__(self, domain: ir.Node, values: ir.Node, lower: ir.Node, upper: ir.Node):
        super().__init__(domain, values, lower, upper)


# Future-extensible placeholders (Graph, Relations, etc.) should follow the same pattern:
# define small, composable action nodes that strictly strengthen the store.


# --- Read-only query nodes (guards/helpers) ---

class TacDom(ir.Node):
    """Query the current candidate domain of a variable.

    Children:
      - var: ir.Node
    Returns: List[Int]
    """

    def __init__(self, var: ir.Node):
        super().__init__(var)


class TacTheOne(ir.Node):
    """Return the sole element of a singleton list/domain.

    Children:
      - values: ir.Node (list)
    Returns: Int
    """

    def __init__(self, values: ir.Node):
        super().__init__(values)


class TacContains(ir.Node):
    """Membership test: value ∈ values.

    Children:
      - values: ir.Node (list)
      - value: ir.Node (int)
    Returns: Bool
    """

    def __init__(self, values: ir.Node, value: ir.Node):
        super().__init__(values, value)


class TacCountHas(ir.Node):
    """Count how many variables in a list have domains intersecting a given value set.

    Children:
      - vars: ir.Node (list of variables)
      - values: ir.Node (list of ints)
    Returns: Int
    """

    def __init__(self, vars: ir.Node, values: ir.Node):
        super().__init__(vars, values)


# --- Utility node: concrete list constant (avoids puzzlespec.ir.List quirk) ---

class TacListConst(ir.Node):
    """Concrete list of elements as a Node for tactic sugar helpers.

    Children: [elem_0, ..., elem_n]
    """

    def __init__(self, *elements: ir.Node):
        super().__init__(*elements)


class TacCellAt(ir.Node):
    """Placeholder for the intersection cell of a row (list of cells) and a col (list of cells).

    Children:
      - row_cells: ir.Node (List of CellIdx)
      - col_cells: ir.Node (List of CellIdx)
    Returns: CellIdx
    """

    def __init__(self, row_cells: ir.Node, col_cells: ir.Node):
        super().__init__(row_cells, col_cells)


class TacListEq(ir.Node):
    """Structural equality between two list expressions (e.g., two rows).

    Children:
      - a: ir.Node (list)
      - b: ir.Node (list)
    Returns: Bool
    """

    def __init__(self, a: ir.Node, b: ir.Node):
        super().__init__(a, b)


class TacForEach(ir.Node):
    """Apply an action-producing lambda to each element of a domain.

    Children:
      - domain: ir.Node (list)
      - action_lambda: ir.Node (Lambda bound to an element, returns an action node)
    """

    def __init__(self, domain: ir.Node, action_lambda: ir.Node):
        super().__init__(domain, action_lambda)


