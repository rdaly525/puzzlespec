type Pred a = a -> Bool         -- subset predicate over a universe
type Rel  a = a -> a -> Bool    -- binary relation on a
data  Partition a k             -- quotient of a by some keyOf : a -> k (implicit)
data  Block a                   -- one equivalence class (one block)


select   :: [a] -> Pred a -> [a]
-- Filter a concrete list by a predicate (pure view; symbolic in DSL).

restrict :: Rel a -> Pred a -> Rel a
-- Limit a relation to edges whose endpoints satisfy the predicate.

rclosure :: Rel a -> Rel a
-- Reflexive–transitive closure (path existence along the relation).

quotient :: [a] -> Rel a -> Partition a k
-- Partition the universe into equivalence classes induced by the relation.

color    :: [a] -> (a -> k) -> Partition a k
-- Partition by a given key function (blocks are fibers of that key).

countKeys  :: Partition a k -> Int
-- Number of blocks (distinct keys that actually occur).

forallKeys :: Partition a k -> (k -> Bool) -> Bool
existsKey  :: Partition a k -> (k -> Bool) -> Bool
-- Quantify over blocks via their keys.

memberAt   :: Partition a k -> k -> Pred a
-- Membership predicate for the block identified by key k.

sizeAt     :: Partition a k -> k -> Int
-- Cardinality (size) of the block at key k.

countBlocks  :: Partition a k -> Int
forallBlocks :: Partition a k -> (Block a -> Bool) -> Bool
existsBlock  :: Partition a k -> (Block a -> Bool) -> Bool
contains     :: Block a -> Pred a
blockSize    :: Block a -> Int
-- Same power as key-based ops; just hides keys and hands you block handles.

touchesAt :: Rel a -> Partition a k -> k -> k -> Bool
-- True iff some element of block k1 relates (via Rel) to some element of block k2.

touches    :: Rel a -> Block a -> Block a -> Bool
-- Keyless version: blocks touch under the relation.

tiles    :: Grid -> (Int,Int) -> [[Cell]]
-- All sliding windows of the given size (row-major order).

anyCell  :: [Cell] -> (Cell -> Bool) -> Bool
allCells :: [Cell] -> (Cell -> Bool) -> Bool
-- Existential/universal tests over a window (compose local rules, e.g., 2×2).

refine  :: Partition a k1 -> (a -> k2) -> Partition a (k1,k2)
-- “Group of groups”: sub-partition each block by a second key; new key is a tuple.

coarsen :: Partition a (k1,k2) -> Partition a k1
-- Drop the secondary key; merge sub-blocks back to their parent block.
connectedRel :: Pred a -> Rel a -> Rel a
-- rclosure (restrict Rel Pred): connectivity inside a predicate.

connectedAt  :: Rel a -> Partition a k -> k -> Bool
-- The k-block is one connected piece under Rel (i.e., quotient … has 1 block).


Mental model

Use quotient for true components (e.g., 4-connected land → islands).

Use color when you already have labels and want blocks as key fibers.

Write rules with forallKeys / forallBlocks, memberAt/contains, and sizeAt/blockSize.

Local bans (like “no 2×2 water”) use tiles + anyCell/allCells.

Mixed properties (e.g., per-island metrics) use refine to attach another key and constrain per (k1,k2).