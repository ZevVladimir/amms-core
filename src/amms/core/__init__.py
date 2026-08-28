"""
The AMMS core creates a standardized snapshot I/O, analysis, plotting, HPC helpers, run metadata for all projects to base off of

Don't have src/amms/__init__.py to allow for future repos like amms-viz

Don't re-export here to avoid circular imports and dragging in all submodules
Specifically load from the module that contains the desired code
"""

__version__ = "0.1.0"
