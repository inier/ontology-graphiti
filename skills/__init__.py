"""Backward compatibility shim for skills module.

.. deprecated::
    Import from odap.tools.base instead.
"""
import warnings
warnings.warn(
    "Importing from 'skills' is deprecated. Use 'odap.tools.base' or specific tool modules.",
    DeprecationWarning,
    stacklevel=2
)

from odap.tools.base import BaseSkill, SkillInput, SkillOutput
from odap.tools.registry import SkillRegistry, register_skill, SKILL_CATALOG

__all__ = [
    'BaseSkill',
    'SkillInput',
    'SkillOutput',
    'SkillRegistry',
    'register_skill',
    'SKILL_CATALOG',
]
