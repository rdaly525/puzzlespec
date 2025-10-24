# Clue Setter API Specification

## Overview

This specification defines a new API for programmatically setting generator variables (gen_vars) in PuzzleSpec objects. The API allows users to set clue values through a context manager that provides typed wrappers for each gen_var, validates assignments, and produces a new PuzzleSpec with the clues substituted.

## Prerequisites

```python
def concretize_indices(self, index_format='tuple') -> 'PuzzleSpec':
    """
    Concretize abstract index types (CellIdxT, EdgeIdxT, etc.) to concrete types.
    
    Args:
        index_format: 'tuple' or 'linear'
            - 'tuple': CellIdxT → Tuple[Int, Int] 
            - 'linear': CellIdxT → Int
    
    Returns:
        New PuzzleSpec with concretized index types
        
    Raises:
        RuntimeError: If index format already set to different value
    """
```

## API Design

### Basic Usage Pattern

```python
# 1. Set parameters and concretize indices
game = Unruly.set_params(nR=4, nC=4)

# 2. Use clue setter context manager
with game.clue_setter(index_format='tuple') as cs:
   
    # Bulk set values  
    cs.given_mask.set(np.zeros((4,4), dtype=bool))
    cs.given_vals.set([[0,1,0,1], [1,0,1,0], [0,1,0,1], [1,0,1,0]])

    # Set individual values
    cs.given_mask[(2,3)] = True
    cs.given_vals[(2,3)] = 1
 
# 3. Finalize to get new PuzzleSpec with clues
game_with_clues = cs.finalize()
```

### Context Manager Interface

```python
def clue_setter(self, index_format='tuple') -> ClueSetter:
    """
    Create a clue setter context manager for setting gen_vars.
    
    Args:
        index_format: 'tuple' (default) or 'linear'
    
    Preconditions:
        - PuzzleSpec must be frozen
        - All parameters must be set (len(self.params) == 0)
        - Topology must have concrete dimensions
        
    Behavior:
        - Auto-calls concretize_indices(index_format) if not already concretized
        - Errors if trying to set different index_format than already set
        
    Returns:
        ClueSetter context manager
    """
```

## Typed Wrapper System

### Core Principle
Each gen_var gets a typed wrapper that corresponds exactly to its IR type and node. Wrappers compose naturally for nested structures by creating child wrappers on-demand when accessed via indexing operations.

### Wrapper Hierarchy

```python
class ClueVar:
    """Base class for all clue variable wrappers"""
    def __init__(self, ir_type, ir_node):
        self.ir_type = ir_type  # The concrete IR type (e.g., irT.Dict[irT.Tuple[irT.Int, irT.Int], irT.Bool])
        self.ir_node = ir_node  # The corresponding IR node (e.g., ir.VarDict)
    
    def set(self, value):
        """Universal set method available on all wrappers"""
        # Validate and store value according to this wrapper's type
        pass

class DictClueVar(ClueVar):
    """Handles Dict[KeyT, ValueT] gen_vars"""
    def __getitem__(self, key):
        # Returns a wrapper for ValueT
        value_type = self.ir_type.valT
        # Create appropriate wrapper for the value type
        return _create_wrapper(value_type, None)  # ir_node=None for nested access
    
    def __setitem__(self, key, value):
        # Validate key format and value type, store in internal dict
        pass
    
    def set(self, dict_data):
        # Bulk assignment: validate entire dict structure
        pass

class ListClueVar(ClueVar):
    """Handles List[ElemT] gen_vars"""  
    def __getitem__(self, index):
        # Returns a wrapper for ElemT
        elem_type = self.ir_type.elemT
        # Create appropriate wrapper for the element type
        return _create_wrapper(elem_type, None)  # ir_node=None for nested access
    
    def __setitem__(self, index, value):
        # Validate index bounds and value type, store in internal list
        pass
    
    def set(self, list_data):
        # Bulk assignment: validate entire list structure
        pass
    
    def append(self, value):
        # Validate value type and append to internal list
        pass

class ScalarClueVar(ClueVar):
    """Handles Bool, Int, FinInt[1,9], etc."""
    def set(self, value):
        # Validate scalar type and store
        pass
    
    # No indexing operations available
```

### Wrapper Creation Pattern Matching

```python
def _create_wrapper(ir_type, ir_node):
    """Create appropriate wrapper based on IR type"""
    if isinstance(ir_type, irT.Dict):
        return DictClueVar(ir_type, ir_node)
    elif isinstance(ir_type, irT.List):
        return ListClueVar(ir_type, ir_node)
    elif ir_type in (irT.Bool, irT.Int, irT.FinInt):
        return ScalarClueVar(ir_type, ir_node)
    else:
        raise ValueError(f"Unsupported clue var type: {ir_type}")
```

### Nested Structure Examples

#### German Whispers: `List[List[CellIdxT]]`
After concretization: `List[List[Tuple[Int, Int]]]`

```python
# Access pattern builds nested wrappers:
cs.german_whispers                    # ListClueVar[List[Tuple[Int, Int]]]
cs.german_whispers[4]                 # ListClueVar[Tuple[Int, Int]] (created on-demand)
cs.german_whispers[4].set([(0,0), (0,1), (0,2)])  # ScalarClueVar for each tuple

# Bulk operations work at any level:
cs.german_whispers.set([              # Set entire whisper structure
    [(0,0), (0,1), (0,2)],           # Whisper line 0
    [(1,0), (1,1), (1,2), (1,3)],   # Whisper line 1  
    [(2,0), (2,1)]                   # Whisper line 2
])

cs.german_whispers[4].set([(0,0), (0,1)])  # Set individual whisper line
```

#### Unruly Givens: `Dict[CellIdxT, Bool]`
After concretization: `Dict[Tuple[Int, Int], Bool]`

```python
cs.given_mask                         # DictClueVar[Tuple[Int, Int], Bool]
cs.given_mask[(2,3)]                  # ScalarClueVar[Bool] (created on-demand)
cs.given_mask[(2,3)].set(True)        # Or direct assignment: cs.given_mask[(2,3)] = True

# Bulk operations:
cs.given_mask.set({(0,0): True, (1,1): False})  # Dict format
cs.given_mask.set([[True, False, True, False],  # 2D list format (for tuple index_format)
                   [False, True, False, True],
                   [True, False, True, False],
                   [False, True, False, True]])
```

## Validation Rules

### Index Format Validation
**Strict validation**: Only accept input formats that match the chosen index_format.

**Tuple format** (`index_format='tuple'`):
- ✅ Accept: 2D lists, dicts with tuple keys, individual tuple assignments
- ❌ Reject: 1D lists, dicts with int keys, individual int assignments

**Linear format** (`index_format='linear'`):
- ✅ Accept: 1D lists, dicts with int keys, individual int assignments  
- ❌ Reject: 2D lists, dicts with tuple keys, individual tuple assignments

### Type Coercion
- **Bool values**: Accept `(0, 1, False, True)` and cast to appropriate bool type
- **Numeric values**: Validate ranges for `FinInt[min,max]` types
- **NumPy arrays**: Convert numpy dtypes to Python types automatically

### Shape Validation
**Exact shape matching required**:
```python
# For 4x4 grid:
# Tuple format:
cs.var.set(np.zeros((4,4)))  # ✅ Correct shape
cs.var.set(np.zeros(16))     # ❌ Wrong shape for tuple format

# Linear format:  
cs.var.set(np.zeros(16))     # ✅ Correct shape
cs.var.set(np.zeros((4,4)))  # ❌ Wrong shape for linear format
```

## Size Constraint System

### 2x2 Framework
Handle size validation based on whether sizes are literals or expressions:

| | **Size is Literal** | **Size is Expression** |
|---|---|---|
| **Bulk set (.set())** | Direct validation: `len(input) == literal` | Add constraint: `len(gen_var) == size_expr` |
| **Individual set** | Direct bounds: `0 <= index < literal` | Add constraint: `index < size_expr` |

### Constant Folding
At `clue_setter()` creation, run `ConstPropPass` on all gen_var size expressions to resolve any expressions that can be evaluated to literals.

### Side Constraints
For expression sizes (containing unresolved gen_vars), add constraints using existing DSL:

```python
# For bulk assignment where size depends on other gen_vars:
constraint = len(gen_var) == size_expression  # Valid DSL syntax

# For individual assignment:
constraint = index < size_expression  # Valid DSL syntax

# Store constraints for later:
self.side_constraints.append(constraint)
```

### Size Expression Access
Access size expressions from IR nodes:
```python
# For VarList nodes:
size_expr = var_list_node._children[0]  # First child is size expression

# For VarDict nodes:
keys_node = var_dict_node._children[0]  # First child is keys (which has size)
size_expr = keys_node._children[0]      # Size of the keys list
```

## Error Handling

### Validation Timing
- **Immediate**: Type validation, format validation, bounds checking for literal sizes
- **Deferred**: Size constraints involving expressions with unresolved gen_vars

### Error Messages
Provide specific error messages:
- Dimension mismatches: "Expected 4x4 array for given_mask, got 2x3"
- Type errors: "Expected bool value, got string 'invalid'"
- Format errors: "Expected tuple indices for tuple format, got integer"
- Bounds errors: "Index (10,10) out of bounds for 4x4 grid"

### Precondition Validation
At `clue_setter()` creation, validate:
- `len(spec.params) == 0` - "Parameters nC not set"
- Topology has concrete dimensions
- Index format conflicts - "Index format already set to 'tuple'"

## Last Write Wins Semantics

Support the pattern of bulk initialization followed by individual overrides:

```python
with game.clue_setter() as cs:
    # Bulk initialize
    cs.given_mask.set(np.zeros((4,4), dtype=bool))
    cs.given_vals.set(np.zeros((4,4), dtype=int))
    
    # Individual overrides
    cs.given_mask[(2,3)] = True
    cs.given_vals[(2,3)] = 1
```

## Implementation Architecture

### ClueSetter Class

```python
class ClueSetter:
    def __init__(self, spec: PuzzleSpec, index_format: str):
        self.spec = spec
        self.index_format = index_format
        self.gen_var_values = {}  # Central storage for all values
        self.side_constraints = []  # List of ast.BoolExpr constraints
        self._finalized = False
        
        # Validate preconditions
        self._validate_preconditions()
        
        # Run constant folding on size expressions
        self._fold_sizes()
        
        # Create typed wrappers for each gen_var
        for name, gen_var in spec.gen_vars.items():
            wrapper = _create_wrapper(gen_var.T, gen_var.node)
            setattr(self, name, wrapper)
    
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
        
    def finalize(self) -> PuzzleSpec:
        """Create new PuzzleSpec with gen_vars substituted and constraints added"""
        if self._finalized:
            raise RuntimeError("ClueSetter already finalized")
        self._finalized = True
        
        # Create new spec with gen_vars substituted using VarSubPass
        new_spec = self._substitute_gen_vars()
        
        # Add all side constraints as puzzle rules
        for constraint in self.side_constraints:
            new_spec += constraint
            
        return new_spec
```

### Variable Substitution
Use existing `VarSubPass` with `target="generator"` to substitute gen_var values in the new PuzzleSpec.

### Constraint Integration
Add side constraints as regular puzzle rules using the existing `+=` operator on PuzzleSpec.

## Complex Nested Examples

### Triple Nested: `List[Dict[CellIdxT, List[FinInt[1,9]]]]`
After concretization: `List[Dict[Tuple[Int, Int], List[FinInt[1,9]]]]`

```python
# Access builds wrappers at each level:
cs.complex_var                       # ListClueVar[Dict[Tuple[Int, Int], List[FinInt[1,9]]]]
cs.complex_var[0]                     # DictClueVar[Tuple[Int, Int], List[FinInt[1,9]]]
cs.complex_var[0][(2,3)]              # ListClueVar[FinInt[1,9]]
cs.complex_var[0][(2,3)][1]           # ScalarClueVar[FinInt[1,9]]

# Set at any level:
cs.complex_var[0][(2,3)].set([1, 5, 9])           # Set list of numbers
cs.complex_var[0].set({(0,0): [1,2], (1,1): [3]}) # Set dict of lists
cs.complex_var.set([{...}, {...}])                # Set entire structure
```

## Future Extensions

### Phase 1 Scope (Initial Implementation)
- `Dict[IndexT, ValueT]` where IndexT is concretized index type
- `List[ValueT]` where ValueT is scalar or index type
- Arbitrary nesting depth
- Only support Bool and Int

### Phase 2 Scope (Future)
- Support for EdgeIdxT, VertexIdxT beyond CellIdxT
- Support for FinInt
- Pre-validation options for immediate constraint checking

## Testing Requirements

### Unit Tests
- Wrapper creation for different IR types
- Nested wrapper creation on-demand
- Validation rules for each index format
- Type coercion behavior
- Error message accuracy

### Integration Tests  
- End-to-end clue setting workflow
- Complex nested structure access patterns
- Constraint generation and solving
- Interaction with existing PuzzleSpec methods
- Performance with large gen_var structures

### Edge Cases
- Deep nesting levels
- Empty assignments
- Boundary value testing
- Constraint conflicts
- Memory usage with large structures

This specification provides a complete, implementable design for the clue setter API that uses typed AST-like wrappers to handle arbitrary nesting levels while leveraging existing infrastructure for validation and constraint solving.
