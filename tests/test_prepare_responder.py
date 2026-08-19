from pathlib import Path
from unittest import mock

from prepare_debian.tasks import prepare_responder

CONFIG = """[Responder Core]

; Poisoners to start
MDNS = On

; Servers to start
SQL  = On
SMB  = Off
HTTP = On

; Custom challenge
Challenge = Random

[HTTP Server]
Serve-Always = Off
"""


def test_server_profiles_change_only_server_block() -> None:
    enabled = prepare_responder.render_server_profile(CONFIG, enabled=True)
    disabled = prepare_responder.render_server_profile(CONFIG, enabled=False)

    assert "SQL  = On\nSMB  = On\nHTTP = On" in enabled
    assert "SQL  = Off\nSMB  = Off\nHTTP = Off" in disabled
    assert "MDNS = On" in enabled
    assert "MDNS = On" in disabled
    assert "Serve-Always = Off" in enabled
    assert "Serve-Always = Off" in disabled


def test_profiles_are_created_beside_installed_config(tmp_path: Path) -> None:
    config_path = tmp_path / "Responder.conf"
    config_path.write_text(CONFIG, encoding="utf-8")

    assert prepare_responder.create_profiles(config_path) is True

    enabled = tmp_path / "Responder.conf.servers-on"
    disabled = tmp_path / "Responder.conf.servers-off"
    assert "SMB  = On" in enabled.read_text(encoding="utf-8")
    assert "SQL  = Off" in disabled.read_text(encoding="utf-8")


def test_unavailable_apt_package_is_a_successful_skip() -> None:
    with (
        mock.patch.object(
            prepare_responder.apt_utils, "is_package_installed", return_value=False
        ),
        mock.patch.object(
            prepare_responder.apt_utils, "is_package_available", return_value=False
        ),
        mock.patch.object(prepare_responder, "create_profiles") as create,
    ):
        assert prepare_responder.main() is True

    create.assert_not_called()


def test_available_apt_package_is_installed_before_profiles() -> None:
    with (
        mock.patch.object(
            prepare_responder.apt_utils, "is_package_installed", return_value=False
        ),
        mock.patch.object(
            prepare_responder.apt_utils, "is_package_available", return_value=True
        ),
        mock.patch.object(
            prepare_responder.apt_utils, "ensure_apt_package", return_value=True
        ) as install,
        mock.patch.object(
            prepare_responder, "create_profiles", return_value=True
        ) as create,
    ):
        assert prepare_responder.main() is True

    install.assert_called_once_with("responder")
    create.assert_called_once_with()
