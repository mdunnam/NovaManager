"""
Plugin manager for PhotoFlow.

Discovers and runs Python plugins from the ``plugins/`` folder.
Each plugin is a plain ``.py`` file that must define:

    PLUGIN_NAME  = "My Plugin"          # str: shown in the Tools menu
    PLUGIN_DESC  = "What it does"       # str: tooltip in the menu

    def run(photos: list[dict], db) -> str | None:
        '''
        photos  — list of photo dicts currently selected in the Library.
                  Falls back to all photos when nothing is selected.
        db      — PhotoDatabase instance.
        Return a short status string to display in the status bar, or None.
        '''

Plugin files are executed in their own module namespace via importlib so they
cannot accidentally access application-internal state beyond what is passed.
"""
import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional


def _plugins_dir() -> Path:
    """Return the path to the plugins/ folder, creating it if absent."""
    plugins = Path(__file__).parent.parent / 'plugins'
    plugins.mkdir(exist_ok=True)
    return plugins


def discover_plugins() -> list[dict]:
    """Return a list of available plugin metadata dicts.

    Each dict contains: ``path``, ``name``, ``description``.
    Plugins that fail to import are silently skipped so a bad plugin
    never prevents the application from starting.
    """
    found = []
    for py_file in sorted(_plugins_dir().glob('*.py')):
        if py_file.name.startswith('_'):
            continue
        try:
            spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            found.append({
                'path': py_file,
                'name': getattr(mod, 'PLUGIN_NAME', py_file.stem),
                'description': getattr(mod, 'PLUGIN_DESC', ''),
                'module': mod,
            })
        except Exception as exc:
            print(f'[PluginManager] Skipping {py_file.name}: {exc}')
    return found


def run_plugin(plugin: dict, photos: list, db) -> Optional[str]:
    """Execute a plugin's ``run()`` function and return its result string.

    Any exception raised by the plugin is caught to prevent it from
    crashing the host application.
    """
    mod = plugin.get('module')
    if not mod or not hasattr(mod, 'run'):
        return f"Plugin '{plugin['name']}' has no run() function."
    try:
        result = mod.run(photos, db)
        return str(result) if result is not None else None
    except Exception as exc:
        return f"Plugin error: {exc}"
