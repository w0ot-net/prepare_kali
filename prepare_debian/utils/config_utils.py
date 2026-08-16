import json
import os
import re
import tempfile
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any, Optional


class ConfigUpdateError(Exception):
    pass


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    temporary_path: Optional[Path] = None

    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def _merge_json_values(
    target: MutableMapping[str, Any], updates: Mapping[str, Any]
) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_json_values(target[key], value)
        else:
            target[key] = value


def update_json_values(path: Path, updates: Mapping[str, Any]) -> bool:
    if path.exists():
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigUpdateError(
                f"Could not read JSON config {path}: {exc}"
            ) from exc
        if not isinstance(values, dict):
            raise ConfigUpdateError(f"JSON config must contain an object: {path}")
    else:
        values = {}

    before = json.dumps(values, sort_keys=True)
    _merge_json_values(values, updates)
    if json.dumps(values, sort_keys=True) == before:
        return False

    _write_atomic(path, json.dumps(values, indent=2) + "\n")
    return True


def _toml_value(value: object) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    raise ConfigUpdateError(f"Unsupported TOML value: {value!r}")


def update_toml_values(path: Path, updates: Mapping[str, object]) -> bool:
    try:
        content = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as exc:
        raise ConfigUpdateError(f"Could not read TOML config {path}: {exc}") from exc

    lines = content.splitlines(keepends=True)
    first_table = next(
        (index for index, line in enumerate(lines) if line.lstrip().startswith("[")),
        len(lines),
    )
    missing = []

    for key, value in updates.items():
        if re.fullmatch(r"[A-Za-z0-9_-]+", key) is None:
            raise ConfigUpdateError(f"Unsupported TOML key: {key!r}")

        pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
        matches = [
            index
            for index, line in enumerate(lines[:first_table])
            if pattern.match(line)
        ]
        if len(matches) > 1:
            raise ConfigUpdateError(f"Duplicate TOML key {key!r} in {path}")
        if matches:
            lines[matches[0]] = f"{key} = {_toml_value(value)}\n"
        else:
            missing.append(f"{key} = {_toml_value(value)}\n")

    if missing:
        if first_table > 0 and not lines[first_table - 1].endswith("\n"):
            lines[first_table - 1] += "\n"
        lines[first_table:first_table] = missing

    updated = "".join(lines)
    if updated == content:
        return False

    _write_atomic(path, updated)
    return True
