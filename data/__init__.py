"""
============================================================
  FORGE MASTER — Game data subpackage

  Lazy loaders and canonical naming for the JSON resources stored
  under ``<project_root>/data/``. Anything that needs to read those
  JSON files goes through ``data.libraries`` so the cache is shared.
  Anything that needs age / rarity / slot names goes through
  ``data.canonical``.
============================================================
"""
