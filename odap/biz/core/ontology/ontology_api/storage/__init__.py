"""Ontology API - SQLite 持久化层"""
from .sqlite_ontology_storage import SQLiteOntologyStorage

Storage = SQLiteOntologyStorage

__all__ = ["Storage", "SQLiteOntologyStorage"]
