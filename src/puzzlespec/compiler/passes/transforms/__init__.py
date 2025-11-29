#Import all the transform passes
from .const_fold import ConstFoldPass
from .substitution import SubstitutionPass, SubMapping
from .alg_simplification import AlgebraicSimplificationPass
from .dom_simplification import DomainSimplificationPass
from .beta_reduction import BetaReductionPass
from .canonicalize import CanonicalizePass