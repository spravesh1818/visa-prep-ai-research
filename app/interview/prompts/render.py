"""Safe template rendering for YAML prompt fragments."""

from __future__ import annotations


class _SafeFormat(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render(template: str, **variables: str) -> str:
    """Substitute ``{name}`` placeholders; leave unknown keys untouched."""

    return template.format_map(_SafeFormat(variables))
