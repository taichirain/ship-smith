__version__ = "0.1.0"

try:
    from ._build_info import BUILD_SHA
except ImportError:
    BUILD_SHA = ""

if BUILD_SHA:
    __version__ = f"{__version__}+{BUILD_SHA}"