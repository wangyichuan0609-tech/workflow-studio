"""Shared paths and invocations for Studio-generated Codex skills."""

from __future__ import annotations

import hashlib
from typing import Optional, Tuple


MANAGED_START = "<!-- workflow-studio:start -->"
MANAGED_END = "<!-- workflow-studio:end -->"
MAX_GENERATED_SKILL_NAME_LENGTH = 64
_HASH_LENGTH = 12
_SKILL_PREFIXES = {"agent": "agent-", "workflow": "workflow-"}


def generated_skill_name(kind: str, resource_id: str) -> str:
    """Return the stable Codex skill name for an Agent or Workflow.

    Existing short ids retain their historical names.  Names that would
    exceed Codex's 64-character skill-name limit keep a readable prefix and
    gain a deterministic digest so ids with the same long prefix cannot
    collide.
    """

    try:
        prefix = _SKILL_PREFIXES[kind]
    except KeyError as error:
        raise ValueError(f"Unsupported generated skill kind: {kind}") from error
    identifier = str(resource_id)
    candidate = prefix + identifier
    if len(candidate) <= MAX_GENERATED_SKILL_NAME_LENGTH:
        return candidate
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:_HASH_LENGTH]
    readable_length = (
        MAX_GENERATED_SKILL_NAME_LENGTH
        - len(prefix)
        - 1
        - len(digest)
    )
    return f"{prefix}{identifier[:readable_length]}-{digest}"


def generated_skill_paths(kind: str, resource_id: str) -> Tuple[str, str]:
    root = f".agents/skills/{generated_skill_name(kind, resource_id)}"
    return f"{root}/SKILL.md", f"{root}/agents/openai.yaml"


def generated_skill_invocation(kind: str, resource_id: str) -> str:
    return f"${generated_skill_name(kind, resource_id)}"


def managed_agents_section(text: str) -> Optional[str]:
    """Return the first complete Workflow Studio managed section, if any."""

    start = text.find(MANAGED_START)
    if start < 0:
        return None
    end = text.find(MANAGED_END, start + len(MANAGED_START))
    if end < 0:
        return None
    return text[start : end + len(MANAGED_END)]


def managed_section_mentions_invocation(text: str, invocation: str) -> bool:
    """Check for one exact, rendered skill invocation in the managed block."""

    section = managed_agents_section(text)
    return section is not None and f"`{invocation}`" in section


__all__ = [
    "MANAGED_END",
    "MANAGED_START",
    "MAX_GENERATED_SKILL_NAME_LENGTH",
    "generated_skill_invocation",
    "generated_skill_name",
    "generated_skill_paths",
    "managed_agents_section",
    "managed_section_mentions_invocation",
]
