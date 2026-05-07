from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any

import yaml

PROMPT_ROOT = Path(__file__).resolve().parents[2] / "prompts"
DEFAULT_PROMPT_VERSION = "v1"


class PromptError(RuntimeError):
    pass


@dataclass(frozen=True)
class PromptTemplate:
    id: str
    version: str
    temperature: float
    model_role: str
    schema: dict[str, Any]
    system: str
    user: str


@dataclass(frozen=True)
class RenderedPrompt:
    task_name: str
    id: str
    version: str
    temperature: float
    model_role: str
    schema: dict[str, Any]
    messages: list[dict[str, str]]


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PromptError(f"Prompt file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PromptError(f"Prompt file must contain a YAML object: {path}")
    return data


@lru_cache(maxsize=16)
def load_common_blocks(version: str = DEFAULT_PROMPT_VERSION) -> dict[str, str]:
    path = PROMPT_ROOT / f"_common.{version}.yaml"
    if not path.exists() and version != DEFAULT_PROMPT_VERSION:
        path = PROMPT_ROOT / f"_common.{DEFAULT_PROMPT_VERSION}.yaml"
    data = _read_yaml(path)
    blocks = data.get("blocks")
    if not isinstance(blocks, dict):
        raise PromptError("Common prompt file must contain a blocks object.")
    return {str(name): str(value).strip() for name, value in blocks.items()}


@lru_cache(maxsize=64)
def load_prompt(task_name: str, version: str = DEFAULT_PROMPT_VERSION) -> PromptTemplate:
    data = _read_yaml(PROMPT_ROOT / f"{task_name}.{version}.yaml")
    required_fields = ("id", "version", "temperature", "model_role", "schema", "system", "user")
    missing = [field for field in required_fields if field not in data]
    if missing:
        raise PromptError(f"Prompt {task_name}.{version} is missing fields: {', '.join(missing)}")
    if not isinstance(data["schema"], dict):
        raise PromptError(f"Prompt {task_name}.{version} schema must be an object.")
    return PromptTemplate(
        id=str(data["id"]),
        version=str(data["version"]),
        temperature=float(data["temperature"]),
        model_role=str(data["model_role"]),
        schema=data["schema"],
        system=str(data["system"]).strip(),
        user=str(data["user"]).strip(),
    )


def render_prompt(
    task_name: str,
    *,
    payload: dict[str, Any],
    version: str = DEFAULT_PROMPT_VERSION,
    attempt: int = 0,
    repair_feedback: str = "",
    variables: dict[str, Any] | None = None,
) -> RenderedPrompt:
    prompt = load_prompt(task_name, version)
    common = {
        f"common_{name}": block
        for name, block in load_common_blocks(version).items()
    }
    render_payload = {
        **payload,
        "attempt": attempt + 1,
        "repairFeedback": repair_feedback,
    }
    template_variables = {
        **common,
        "payload_json": json.dumps(render_payload, ensure_ascii=False),
        "attempt": str(attempt + 1),
        "repair_feedback": repair_feedback,
        **{key: str(value) for key, value in (variables or {}).items()},
    }
    try:
        system = Template(prompt.system).substitute(template_variables)
        user = Template(prompt.user).substitute(template_variables)
    except KeyError as error:
        raise PromptError(f"Missing template variable {error} for prompt {prompt.id}.{prompt.version}") from None
    return RenderedPrompt(
        task_name=task_name,
        id=prompt.id,
        version=prompt.version,
        temperature=prompt.temperature,
        model_role=prompt.model_role,
        schema=prompt.schema,
        messages=[
            {"role": "system", "content": system.strip()},
            {"role": "user", "content": user.strip()},
        ],
    )
