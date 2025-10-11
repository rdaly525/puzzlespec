#Import all the transform passes
from .const_fold import ConstFoldPass
from .substitution import SubstitutionPass, SubMapping
from .resolve_bound_vars import ResolveBoundVars
from .simplification import AlgebraicSimplificationPass