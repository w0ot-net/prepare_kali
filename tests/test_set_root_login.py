import stat
from pathlib import Path
from unittest import mock

import pytest

from prepare_debian.tasks import set_root_login


def test_accounts_service_root_is_made_visible_without_losing_other_values() -> None:
    original = """# Managed by AccountsService
[User]
Language=en_US.UTF-8
SystemAccount=true

[InputSource0]
xkb=us
"""

    rendered = set_root_login.render_accounts_service_user(original)

    assert "Language=en_US.UTF-8" in rendered
    assert "[InputSource0]\nxkb=us" in rendered
    assert "SystemAccount=false" in rendered
    assert "SystemAccount=true" not in rendered
    assert set_root_login.render_accounts_service_user(rendered) == rendered


def test_duplicate_accounts_service_values_are_rejected() -> None:
    content = """[User]
SystemAccount=true
SystemAccount=false
"""

    with pytest.raises(ValueError, match="duplicate SystemAccount"):
        set_root_login.render_accounts_service_user(content)


def test_login_screen_configuration_is_persistent_and_preserves_modes(
    tmp_path: Path,
) -> None:
    accounts = tmp_path / "AccountsService" / "users" / "root"
    accounts.parent.mkdir(parents=True)
    accounts.write_text("[User]\nSystemAccount=true\n", encoding="utf-8")
    accounts.chmod(0o640)
    lightdm = tmp_path / "lightdm" / "lightdm.conf.d" / "root.conf"

    assert set_root_login.configure_login_screen(accounts, lightdm) is True
    assert set_root_login.configure_login_screen(accounts, lightdm) is True

    assert accounts.read_text(encoding="utf-8") == "[User]\nSystemAccount=false\n"
    assert stat.S_IMODE(accounts.stat().st_mode) == 0o640
    assert lightdm.read_text(encoding="utf-8") == set_root_login.LIGHTDM_CONFIG
    assert stat.S_IMODE(lightdm.stat().st_mode) == 0o644


def test_task_installs_missing_kali_package_before_configuring() -> None:
    with (
        mock.patch.object(set_root_login.os, "geteuid", return_value=0),
        mock.patch.object(
            set_root_login.apt_utils,
            "is_package_installed",
            side_effect=(False, False),
        ) as check,
        mock.patch.object(
            set_root_login.apt_utils, "update_apt_cache", return_value=True
        ) as update,
        mock.patch.object(
            set_root_login.apt_utils, "ensure_apt_package", return_value=True
        ) as install,
        mock.patch.object(
            set_root_login, "configure_login_screen", return_value=True
        ) as configure,
    ):
        assert set_root_login.main() is True

    update.assert_called_once_with()
    assert check.call_args_list == [
        mock.call("accountsservice"),
        mock.call("kali-root-login"),
    ]
    assert install.call_args_list == [
        mock.call("accountsservice"),
        mock.call("kali-root-login"),
    ]
    configure.assert_called_once_with()


def test_task_requires_effective_root_privileges() -> None:
    with (
        mock.patch.object(set_root_login.os, "geteuid", return_value=1000),
        mock.patch.object(set_root_login.apt_utils, "is_package_installed") as check,
    ):
        assert set_root_login.main() is False

    check.assert_not_called()
