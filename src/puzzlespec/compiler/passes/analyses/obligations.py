from __future__ import annotations

import typing as tp

from puzzlespec.compiler.passes.envobj import EnvsObj

from ..pass_base import Analysis, AnalysisObject, Context, handles
from ...dsl import ir, ir_types as irT


class ObligationsResults(AnalysisObject):
    """Template analysis result object."""
    def __init__(self, data: tp.Any):
        self.data = data


class ObligationsPass(Analysis):
    """Template for creating new Analysis passes.
    
    This template provides visitor methods for all IR node types in the same order
    as they are declared in ir.py. Copy this file and modify as needed for your
    specific analysis pass.
    """

    requires = (EnvsObj,)  # Add required analysis dependencies here
    produces = (ObligationsResults,)  # Add produced analysis objects here
    name = "template_analysis"

    def run(self, root: ir.Node, ctx: Context) -> AnalysisObject:
        """Main entry point for the analysis pass."""
        # Initialize any state needed for the analysis
        self.state = {}
        
        # Perform the analysis by visiting the root node
        result = self.visit(root)
        
        # Package and return the result
        analysis_result = TemplateAnalysisResult(result)
        ctx.add(analysis_result)
        return analysis_result

    def visit(self, node: ir.Node) -> tp.Any:
        """Visit a node and return the analysis result."""
        # This method is inherited from the base Analysis class
        # It will automatically dispatch to the appropriate visitor method
        return super().visit(node)

    ##############################
    ## Core-level IR nodes (Used throughout entire compiler flow)
    ##############################

    @handles(ir.Eq)
    def _(self, node: ir.Eq) -> tp.Any:
        """Analyze equality nodes."""
        # TODO: Implement analysis for Eq nodes
        left, right = self.visit_children(node)
        return (left, right)

    @handles(ir.Div)
    def _(self, node: ir.Div) -> tp.Any:
        """Analyze division nodes."""
        # TODO: Implement analysis for Div nodes
        left, right = self.visit_children(node)
        return (left, right)

    @handles(ir.Mod)
    def _(self, node: ir.Mod) -> tp.Any:
        """Analyze modulo nodes."""
        # TODO: Implement analysis for Mod nodes
        left, right = self.visit_children(node)
        return (left, right)

    @handles(ir.Fin)
    def _(self, node: ir.Fin) -> tp.Any:
        """Analyze finite domain nodes."""
        # TODO: Implement analysis for Fin nodes
        N, = self.visit_children(node)
        return N

    @handles(ir.IsMember)
    def _(self, node: ir.IsMember) -> tp.Any:
        """Analyze is member nodes."""
        # TODO: Implement analysis for IsMember nodes
        domain, val = self.visit_children(node)
        return (domain, val)

    @handles(ir.Tabulate)
    def _(self, node: ir.Tabulate) -> tp.Any:
        """Analyze tabulate nodes."""
        # TODO: Implement analysis for Tabulate nodes
        dom, fun = self.visit_children(node)
        return (dom, fun)

    @handles(ir.ImageOf)
    def _(self, node: ir.ImageOf) -> tp.Any:
        """Analyze image of nodes."""
        # TODO: Implement analysis for ImageOf nodes
        func, = self.visit_children(node)
        return func

    @handles(ir.Apply)
    def _(self, node: ir.Apply) -> tp.Any:
        """Analyze apply nodes."""
        # TODO: Implement analysis for Apply nodes
        func, arg = self.visit_children(node)
        return (func, arg)

    @handles(ir.Windows)
    def _(self, node: ir.Windows) -> tp.Any:

        # Window operation soundness: size > 0, stride > 0, L >= size, and (L - size) divisible by stride
        """Analyze windows nodes."""
        # TODO: Implement analysis for Windows nodes
        list_node, size, stride = self.visit_children(node)
        return (list_node, size, stride)

    @handles(ir.Tiles)
    def _(self, node: ir.Tiles) -> tp.Any:
        """Analyze tiles nodes."""
        # TODO: Implement analysis for Tiles nodes
        grid, size_r, size_c, stride_r, stride_c = self.visit_children(node)
        return (grid, size_r, size_c, stride_r, stride_c)
