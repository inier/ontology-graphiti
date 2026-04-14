"""Backward compatibility shim for ontology module.

.. deprecated::
    Import from odap.biz.ontology instead.
"""
import warnings
warnings.warn(
    "Importing from 'ontology' is deprecated. Use 'odap.biz.ontology' instead.",
    DeprecationWarning,
    stacklevel=2
)

from odap.biz.ontology.service import OntologyManager

__all__ = ['OntologyManager']
