"""Prompt templates (ai/prompts/*.md), rendered with Jinja2 in strict mode."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_env = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    undefined=StrictUndefined,
    autoescape=False,  # plain-text prompts, not HTML
    keep_trailing_newline=True,
)


def to_json(data: Any) -> str:
    return json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False)


def system_prompt() -> str:
    return _env.get_template("system.md").render()


def render(name: str, **context: Any) -> str:
    """Render `prompts/<name>.md`; dict/list values are embedded as JSON."""
    values = {k: to_json(v) if isinstance(v, dict | list) else v for k, v in context.items()}
    return _env.get_template(f"{name}.md").render(**values)
