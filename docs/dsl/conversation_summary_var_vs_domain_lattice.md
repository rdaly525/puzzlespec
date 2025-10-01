# Conversation Summary – Views, Isomorphisms, Abstractions, Lattice, and Var vs Domain in Puzzle DSL

## 1. View Graph and Lattice Model

We model puzzle state representations as **views** arranged in a **lattice/DAG**:

- **Nodes** = views (variable views, domain views, abstract views)
- **Edges** = *connections* that describe exact or approximate relationships.

### Connection Types (meta-definitions)

**1. Isomorphism (↔)**
- **Meaning:** Lossless, bijective mapping between two views.
- **Formal:** ∃f, f⁻¹ such that f⁻¹(f(x)) = x and f(f⁻¹(y)) = y for all states.
- **Example:** `CellDigit` ↔ `DigitPlacement` (cell-centric vs unit-centric assignments).

**2. Abstraction (α) and Concretization (γ)**
- **Meaning:** α maps a more concrete view to a coarser one; γ maps abstract elements back to sets of concretes.
- **Formal:** (α, γ) form a **Galois connection**:  
  α(c) ≤ a  ⇔  c ∈ γ(a)
- **Example:** Digit {1..9} → L/M/H classes for German Whisper constraints.

**3. Domain–Variable Channeling**
- **Meaning:** Domain view represents the set of possible values for a variable view.
- **Formal:** For variable X with domain D:  
  X = v ⇒ v ∈ Dom(X) ∧ ∀w≠v: w ∉ Dom(X)  
  w ∉ Dom(X) ⇒ X ≠ w  
  |Dom(X)| = 1 ⇒ X = the only element.

### Lattice Perspective
- **Bottom**: fully concrete assignment (primary variable view).
- **Horizontal edges**: isomorphisms to alternative but equally concrete representations.
- **Upward edges**: abstractions (α) lose detail.
- **Downward edges**: concretization (γ) expand abstract states into all consistent concrete states.

---

## 2. Variable Views vs Domain Views

**Variable view**
- Represents the *actual* value of a variable.
- Examples:  
  - `CellDigit[c] ∈ {1..9}`  
  - `DigitPlacement[U,d] ∈ U`

**Domain view**
- Represents the **set of possible values** for that variable during solving.
- Examples:  
  - `AllowCell[c] ⊆ {1..9}`  
  - `UnitPos[U,d] ⊆ U`

**Relationship:** Domain views are the **domain abstraction** of variable views.

---

## 3. Implications for DSL & Compiler Design

**Puzzle specification (rulesets)**
- Use a **primary variable view** as the canonical representation.
- Keep optional isomorphic variable views for convenience.
- Avoid embedding domain views in base rules.

**Tactic authoring**
- Guards: domain views (pattern-rich).
- Actions: standardized API on primary variable view.
- Compiler: channel actions to other views.

**Compiler responsibilities**
- Maintain invariants for all view connections.
- Provide canonicalization between views.
- Materialize domain views lazily.

---

## 4. Channeling Example: Sudoku UnitPos ↔ DigitPlacement

**Variable view:** `DigitPlacement[U,d]` = chosen cell in U for digit d.  
**Domain view:** `UnitPos[U,d]` = allowed cells in U for digit d.

**Channeling constraints:**
1. `DigitPlacement[U,d] = c ⇒ c ∈ UnitPos[U,d]`
2. `DigitPlacement[U,d] = c ⇒ ∀c'≠c: c' ∉ UnitPos[U,d]`
3. `c ∉ UnitPos[U,d] ⇒ DigitPlacement[U,d] ≠ c`
4. `|UnitPos[U,d]|=1 ⇒ DigitPlacement[U,d]` = the only element.

---

## 5. Recommended Practice
- **Specs:** rules over primary variable view.
- **Tactics:** guards in domain views, actions in variable view.
- **Compiler:** auto-channel and sync views; canonicalize for proofs.

---

## 6. Benefits
- Clarity in specs and tactics.
- Proof-friendly invariants.
- Reuse via abstraction lifting.
- Efficiency by avoiding duplicate base constraints.

