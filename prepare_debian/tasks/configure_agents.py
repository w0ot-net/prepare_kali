import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

from prepare_debian.utils import config_utils, output_utils

CODEX_VALUES: Mapping[str, Any] = {
    "commit_attribution": "",
}

CLAUDE_VALUES: Mapping[str, Any] = {
    "attribution": {
        "commit": "",
        "pr": "",
        "sessionUrl": False,
    },
    "includeCoAuthoredBy": False,
}


def apply_agent_config(home: Path, codex_home: Optional[Path] = None) -> None:
    if codex_home is None:
        configured_codex_home = os.environ.get("CODEX_HOME")
        codex_home = (
            Path(configured_codex_home) if configured_codex_home else home / ".codex"
        )

    codex_path = codex_home / "config.toml"
    claude_path = home / ".claude" / "settings.json"

    codex_changed = config_utils.update_toml_values(codex_path, CODEX_VALUES)
    claude_changed = config_utils.update_json_values(claude_path, CLAUDE_VALUES)

    for name, path, changed in (
        ("Codex", codex_path, codex_changed),
        ("Claude", claude_path, claude_changed),
    ):
        action = "Updated" if changed else "Already configured"
        output_utils.ok(f"{action}: {name} attribution disabled in {path}")


def main(force: bool = False) -> bool:
    del force
    try:
        apply_agent_config(Path.home())
    except (config_utils.ConfigUpdateError, OSError) as exc:
        output_utils.warn(str(exc))
        return False
    return True
