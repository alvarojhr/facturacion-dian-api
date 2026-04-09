#!/usr/bin/env python3
"""Validate the bundled DIAN integration skill and its agent metadata."""

from __future__ import annotations

import sys
from pathlib import Path


def read_text(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"Missing required file: {path}")
    return path.read_text(encoding="utf-8")


def parse_frontmatter(skill_text: str) -> dict[str, str]:
    lines = skill_text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter")

    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            raise ValueError(f"Invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')

    for key in ("name", "description"):
        if not data.get(key):
            raise ValueError(f"Missing frontmatter field: {key}")
    return data


def parse_openai_yaml(yaml_text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    current_section: str | None = None

    for raw_line in yaml_text.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if not line.startswith(" "):
            if not line.endswith(":"):
                raise ValueError(f"Invalid top-level YAML line: {line}")
            current_section = line[:-1]
            continue

        if current_section is None:
            raise ValueError(f"Unexpected indented YAML line: {line}")

        stripped = line.strip()
        if ":" not in stripped:
            raise ValueError(f"Invalid YAML mapping line: {line}")

        key, value = stripped.split(":", 1)
        parsed[f"{current_section}.{key.strip()}"] = value.strip().strip('"')

    required = {
        "interface.display_name",
        "interface.short_description",
        "interface.default_prompt",
        "policy.allow_implicit_invocation",
    }
    missing = sorted(required - parsed.keys())
    if missing:
        raise ValueError(f"Missing openai.yaml keys: {', '.join(missing)}")
    return parsed


def validate_skill(skill_dir: Path) -> None:
    skill_path = skill_dir / "SKILL.md"
    openai_path = skill_dir / "agents" / "openai.yaml"
    references_dir = skill_dir / "references"

    skill_text = read_text(skill_path)
    frontmatter = parse_frontmatter(skill_text)
    openai = parse_openai_yaml(read_text(openai_path))

    expected_skill_ref = f"${frontmatter['name']}"
    if expected_skill_ref not in openai["interface.default_prompt"]:
        raise ValueError(
            "agents/openai.yaml default_prompt must reference the skill trigger "
            f"{expected_skill_ref}"
        )

    expected_repo_name = "facturacion-dian-kit"
    for key in ("description",):
        if expected_repo_name not in frontmatter[key]:
            raise ValueError(f"SKILL.md {key} must mention {expected_repo_name}")

    for key in ("interface.short_description", "interface.default_prompt"):
        if expected_repo_name not in openai[key]:
            raise ValueError(f"agents/openai.yaml {key} must mention {expected_repo_name}")

    if openai["policy.allow_implicit_invocation"].lower() != "true":
        raise ValueError("agents/openai.yaml policy.allow_implicit_invocation must be true")

    required_references = (
        "http-api.md",
        "examples.md",
        "troubleshooting.md",
        "habilitacion.md",
    )
    for filename in required_references:
        path = references_dir / filename
        if not path.is_file():
            raise ValueError(f"Missing skill reference: {path}")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    skill_dir = repo_root / ".agents" / "skills" / "dian-integration"
    try:
        validate_skill(skill_dir)
    except ValueError as exc:
        print(f"Skill validation failed: {exc}", file=sys.stderr)
        return 1

    print(f"Skill validation passed: {skill_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
