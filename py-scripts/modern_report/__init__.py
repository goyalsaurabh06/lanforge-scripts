"""Modern LANforge HTML, chart, and PDF reporting package."""

from .lf_modern_graph import (
    lf_bar_graph,
    lf_bar_graph_horizontal,
    lf_line_graph,
    lf_pie_graph,
)
from .lf_modern_report import lf_report

__all__ = [
    "lf_report",
    "lf_bar_graph",
    "lf_bar_graph_horizontal",
    "lf_line_graph",
    "lf_pie_graph",
]
