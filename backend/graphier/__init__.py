"""Graphier: a knowledge workspace where the graph builds itself.

Library use:

    import graphier
    v = graphier.open("~/notes")
    v.plot_graph(); v.plot_timeline()
"""

__version__ = "0.1.0"

from .api import PlotStyle, VaultSession, open  # noqa: F401,A004
