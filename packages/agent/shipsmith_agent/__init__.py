from ._version import BASE_VERSION

try:
    from ._build_info import BUILD_SHA
except ImportError:
    BUILD_SHA = ""

__version__ = BASE_VERSION + (f"+{BUILD_SHA}" if BUILD_SHA else "")