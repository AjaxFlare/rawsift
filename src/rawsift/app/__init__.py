"""Local web application for rawsift.

The import stays lazy so the original command-line culler continues to work
without the optional web-application dependencies.
"""


def create_app(*args, **kwargs):
    from .server import create_app as factory

    return factory(*args, **kwargs)


__all__ = ["create_app"]
