try:
    from importlib.metadata import version

    __version__ = version("open-ephys-audio")
except Exception:
    # If package is not installed (e.g. during development)
    __version__ = "unknown"
