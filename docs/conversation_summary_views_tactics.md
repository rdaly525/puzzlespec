# Conversation Summary – Views, Isomorphisms, Abstractions, and Var vs Domain in Puzzle DSL

## 1. View Graph Model
We treat puzzle state representations as **views**, connected in a graph:

- **Concrete variable views**: full assignments for each puzzle variable.
- **Isomorphic views**: different coordinate systems for the same assignments (lossless).
- **Abstract views**: coarser partitions of domains (via Galois α/γ abstraction).

**Edges**:
- **Horizontal**: isomorphisms (bijective, invertible, exact).
- **Vertical**: abstraction/concretization (loss of detail upward, expansion downward).

---

## 2. Variable Views vs Domain Views

### Variable view
- Represents the variable’s *actual* value.
- Example: `CellDigit[c] ∈ {1..9}` (digit in cell c).
- Example: `DigitPlacement[U,d] ∈ U` (which cell in unit U holds digit d).

### Domain view
- Represents the **set of possible values** for that variable at a given solving state.
- Example: `AllowCell[c] ⊆ {1..9}` (digits still possible for cell c).
- Example: `UnitPos[U,d] ⊆ U` (cells in unit U where digit d could still go).

### Relationship
If `Var` is the variable view and `Dom` its domain view:
- Value → membership: `Var = v ⇒ v ∈ Dom`
- Value → non-membership for others: `Var = v ⇒ ∀w≠v: w ∉ Dom`
- Non-membership → inequality: `v ∉ Dom ⇒ Var ≠ v`
- Singleton domain → value: `|Dom| = 1 ⇒ Var = the only element`

**In a solution**: domain view is a singleton; variable and domain views are isomorphic.  
**During solving**: domain view is an over-approximation (abstraction) of the variable’s value.

---

## 3. Implications for DSL & Compiler Design

### Puzzle specification (rulesets)
- **Primary view** should be a **variable view** (e.g., `CellDigit` or `DigitPlacement`).
- Optional isomorphic variable view if it makes rules clearer.
- **Domain views** (candidates) should not be part of the core rules; they bloat the model and duplicate constraints.

### Tactic authoring
- **Guards (patterns)**: domain views are often more natural (e.g., UnitPos for fish, AllowCell for singles).
- **Actions (effects)**: standardize on a small API acting on the primary variable view (e.g., `place(c,d)`, `forbid(c,d)`).
- Compiler channels actions to all related views via invariants.

### Compiler responsibilities
- **Channeling constraints** (always on) to maintain consistency between variable and domain views.
- **View canonicalization** to store/prove rules in the primary view while preserving pretty forms for explanation.
- **Lazy materialization** of domain views for tactics/UI only.

---

## 4. Channeling Example: Sudoku UnitPos ↔ DigitPlacement

**Variable view**: `DigitPlacement[U,d]` = cell chosen for digit d in unit U.  
**Domain view**: `UnitPos[U,d]` = candidate cells for digit d in unit U.

Channeling:
1. `DigitPlacement[U,d] = c ⇒ c ∈ UnitPos[U,d]`
2. `DigitPlacement[U,d] = c ⇒ ∀c'≠c: c' ∉ UnitPos[U,d]`
3. `c ∉ UnitPos[U,d] ⇒ DigitPlacement[U,d] ≠ c`
4. `|UnitPos[U,d]|=1 ⇒ DigitPlacement[U,d]` = only element

This allows **bidirectional propagation** of information between views at all times.

---

## 5. Recommended Practice
- **Specs**: write constraints over the primary variable view (exact state).
- **Tactics**: match in domain views (compact patterns), act on primary variable view (uniform API).
- **Compiler**: manage all view translations and channeling automatically; avoid burdening the author.

---

## 6. Benefits of This Approach
- Readable, semantically clear specs.
- Proof-friendly: explicit invariants for all view relationships.
- Reusability: abstractions on one view lift automatically to isomorphic siblings.
- Efficient: no duplicate constraints in the base model; domain views exist only where needed.
