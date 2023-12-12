from __future__ import annotations

import importlib
import importlib.util
import pkgutil
import sys
from pathlib import Path
from typing import Type

from .base import PluginABC  # noqa: F401

__all__ = [
    "PluginABC",
    "load_plugins",
]


def get_all_subclasses(cls: Type[PluginABC]) -> set[Type[PluginABC]]:
    return set(cls.__subclasses__()).union([s for c in cls.__subclasses__() for s in get_all_subclasses(c)])


def load_plugins(
    search_directories: list[str | Path] | None = None,
    *,
    verbose: bool = False,
) -> dict[str, Type[PluginABC]]:
    """
    Load plugins from the plugins directory.
    :param search_directories: list of directories to search for plugins
    :param verbose: verbose output
    """
    search_directories = search_directories or []
    search_directories = [Path(__file__).parent] + search_directories  # add local plugins first

    # force load plugins
    print("Loading plugins...")
    for module_info in pkgutil.iter_modules([str(path) for path in search_directories]):
        if module_info.name == "__init__":
            continue
        if verbose:
            print(f"- {module_info.name} from {module_info.module_finder.path}")

        spec = module_info.module_finder.find_spec(fullname=module_info.name)
        module = importlib.util.module_from_spec(spec)
        module.__package__ = __package__  # TODO: check for external plugins

        sys.modules[module_info.name] = module
        spec.loader.exec_module(module)

    # collect plugins as abstract class subclasses
    plugins = {}
    for subclass in get_all_subclasses(PluginABC):
        plugins[subclass.name] = subclass
    if verbose:
        print(f"Loaded: {', '.join(plugins.keys())}")
    return plugins
