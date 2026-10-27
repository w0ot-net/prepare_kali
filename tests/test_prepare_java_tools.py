import io
import json
import os
import zipfile
from pathlib import Path
from unittest import mock

from prepare_debian.tasks import prepare_java_tools


def tool_spec() -> prepare_java_tools.JavaToolSpec:
    return prepare_java_tools.JavaToolSpec(
        name="example",
        repository="owner/example",
        asset_pattern=r"example-all\.jar",
        directory_name="example",
        jar_name="example.jar",
    )


def jar_bytes(main_class: bool = True) -> bytes:
    output = io.BytesIO()
    manifest = "Manifest-Version: 1.0\n"
    if main_class:
        manifest += "Main-Class: example.Main\n"
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("META-INF/MANIFEST.MF", manifest)
    return output.getvalue()


def write_jar(path: Path, main_class: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jar_bytes(main_class))


def test_runnable_jar_requires_main_class(tmp_path: Path) -> None:
    jar = tmp_path / "example.jar"
    write_jar(jar, main_class=False)

    assert prepare_java_tools.is_runnable_jar(jar) is False


def test_latest_release_selects_one_official_matching_jar() -> None:
    payload = {
        "tag_name": "v1.2.3",
        "assets": [
            {
                "name": "notes.txt",
                "browser_download_url": (
                    "https://github.com/owner/example/releases/download/v1.2.3/notes.txt"
                ),
            },
            {
                "name": "example-all.jar",
                "browser_download_url": (
                    "https://github.com/owner/example/releases/download/"
                    "v1.2.3/example-all.jar"
                ),
            },
        ],
    }
    with mock.patch.object(
        prepare_java_tools.urllib.request,
        "urlopen",
        return_value=io.BytesIO(json.dumps(payload).encode()),
    ):
        release = prepare_java_tools.latest_release(tool_spec())

    assert release == prepare_java_tools.Release(
        "v1.2.3",
        "https://github.com/owner/example/releases/download/v1.2.3/example-all.jar",
    )


def test_latest_release_rejects_duplicate_matching_assets() -> None:
    asset = {
        "name": "example-all.jar",
        "browser_download_url": (
            "https://github.com/owner/example/releases/download/v1/example-all.jar"
        ),
    }
    payload = {"tag_name": "v1", "assets": [asset, asset]}
    with mock.patch.object(
        prepare_java_tools.urllib.request,
        "urlopen",
        return_value=io.BytesIO(json.dumps(payload).encode()),
    ):
        assert prepare_java_tools.latest_release(tool_spec()) is None


def test_install_release_is_idempotent_and_updates_managed_jar(
    tmp_path: Path,
) -> None:
    spec = tool_spec()
    first = prepare_java_tools.Release("v1", "https://example/one")
    second = prepare_java_tools.Release("v2", "https://example/two")

    with mock.patch.object(
        prepare_java_tools.urllib.request,
        "urlopen",
        side_effect=[io.BytesIO(jar_bytes()), io.BytesIO(jar_bytes())],
    ) as download:
        assert prepare_java_tools.install_release(spec, first, tmp_path) is True
        assert prepare_java_tools.install_release(spec, first, tmp_path) is True
        assert prepare_java_tools.install_release(spec, second, tmp_path) is True

    destination = prepare_java_tools.jar_path(spec, tmp_path)
    assert prepare_java_tools.is_runnable_jar(destination)
    assert prepare_java_tools.release_path(spec, tmp_path).read_text() == "v2\n"
    assert download.call_count == 2


def test_failed_download_preserves_previous_managed_jar(tmp_path: Path) -> None:
    spec = tool_spec()
    destination = prepare_java_tools.jar_path(spec, tmp_path)
    version = prepare_java_tools.release_path(spec, tmp_path)
    write_jar(destination)
    original = destination.read_bytes()
    version.write_text("v1\n")

    with mock.patch.object(
        prepare_java_tools.urllib.request,
        "urlopen",
        return_value=io.BytesIO(b"not a jar"),
    ):
        assert (
            prepare_java_tools.install_release(
                spec, prepare_java_tools.Release("v2", "https://example/two"), tmp_path
            )
            is False
        )

    assert destination.read_bytes() == original
    assert version.read_text() == "v1\n"


def test_install_release_preserves_unmanaged_destination(tmp_path: Path) -> None:
    spec = tool_spec()
    destination = prepare_java_tools.jar_path(spec, tmp_path)
    write_jar(destination)
    original = destination.read_bytes()

    with mock.patch.object(prepare_java_tools.urllib.request, "urlopen") as download:
        assert (
            prepare_java_tools.install_release(
                spec, prepare_java_tools.Release("v1", "https://example/one"), tmp_path
            )
            is False
        )

    download.assert_not_called()
    assert destination.read_bytes() == original


def test_release_marker_failure_restores_previous_jar(tmp_path: Path) -> None:
    spec = tool_spec()
    destination = prepare_java_tools.jar_path(spec, tmp_path)
    version = prepare_java_tools.release_path(spec, tmp_path)
    write_jar(destination)
    original = destination.read_bytes()
    version.write_text("v1\n")
    real_replace = os.replace

    def fail_marker_replace(source: str, target: str) -> None:
        if Path(target) == version:
            raise OSError("marker write failed")
        real_replace(source, target)

    with (
        mock.patch.object(
            prepare_java_tools.urllib.request,
            "urlopen",
            return_value=io.BytesIO(jar_bytes()),
        ),
        mock.patch.object(
            prepare_java_tools.os, "replace", side_effect=fail_marker_replace
        ),
    ):
        assert (
            prepare_java_tools.install_release(
                spec, prepare_java_tools.Release("v2", "https://example/two"), tmp_path
            )
            is False
        )

    assert destination.read_bytes() == original
    assert version.read_text() == "v1\n"


def test_launcher_is_idempotent_and_preserves_unmanaged_file(tmp_path: Path) -> None:
    spec = tool_spec()
    destination = tmp_path / "tools" / "example.jar"
    launcher = tmp_path / ".local" / "bin" / spec.name

    assert prepare_java_tools.ensure_launcher(spec, destination, tmp_path) is True
    assert prepare_java_tools.ensure_launcher(spec, destination, tmp_path) is True
    assert launcher.stat().st_mode & 0o111
    assert str(destination) in launcher.read_text()

    launcher.write_text("#!/bin/sh\necho custom\n")
    assert prepare_java_tools.ensure_launcher(spec, destination, tmp_path) is False
    assert launcher.read_text() == "#!/bin/sh\necho custom\n"


def test_ysoserial_link_is_absolute_idempotent_and_conflict_safe(
    tmp_path: Path,
) -> None:
    target = tmp_path / "tools" / "ysoserial.jar"
    link = tmp_path / "opt" / "yso.jar"
    write_jar(target)

    assert prepare_java_tools.ensure_ysoserial_link(target, link) is True
    assert prepare_java_tools.ensure_ysoserial_link(target, link) is True
    assert Path(os.readlink(link)).is_absolute()
    assert link.resolve() == target.resolve()

    link.unlink()
    link.write_text("keep\n")
    assert prepare_java_tools.ensure_ysoserial_link(target, link) is False
    assert link.read_text() == "keep\n"


def test_main_requires_root_before_installing_package() -> None:
    with (
        mock.patch.object(prepare_java_tools.os, "geteuid", return_value=1000),
        mock.patch.object(prepare_java_tools.apt_utils, "ensure_apt_package") as apt,
    ):
        assert prepare_java_tools.main() is False

    apt.assert_not_called()


def test_main_stops_when_java_is_missing() -> None:
    with (
        mock.patch.object(prepare_java_tools.os, "geteuid", return_value=0),
        mock.patch.object(
            prepare_java_tools.apt_utils, "ensure_apt_package", return_value=True
        ),
        mock.patch.object(prepare_java_tools.shutil, "which", return_value=None),
        mock.patch.object(prepare_java_tools.set_tools, "ensure_tools_dir") as tools,
    ):
        assert prepare_java_tools.main() is False

    tools.assert_not_called()


def test_main_installs_both_tools_and_compatibility_link() -> None:
    releases = [
        prepare_java_tools.Release("v1", "https://example/beanshooter"),
        prepare_java_tools.Release("v2", "https://example/ysoserial"),
    ]
    with (
        mock.patch.object(prepare_java_tools.os, "geteuid", return_value=0),
        mock.patch.object(
            prepare_java_tools.apt_utils, "ensure_apt_package", return_value=True
        ),
        mock.patch.object(
            prepare_java_tools.shutil, "which", return_value="/usr/bin/java"
        ),
        mock.patch.object(
            prepare_java_tools.set_tools, "ensure_tools_dir", return_value=True
        ),
        mock.patch.object(
            prepare_java_tools.configure_agents,
            "ensure_local_bin_on_path",
            return_value=True,
        ),
        mock.patch.object(prepare_java_tools, "latest_release", side_effect=releases),
        mock.patch.object(
            prepare_java_tools, "install_release", return_value=True
        ) as install,
        mock.patch.object(
            prepare_java_tools, "ensure_launcher", return_value=True
        ) as launcher,
        mock.patch.object(
            prepare_java_tools, "ensure_ysoserial_link", return_value=True
        ) as compatibility_link,
    ):
        assert prepare_java_tools.main() is True

    assert install.call_count == 2
    assert launcher.call_count == 2
    compatibility_link.assert_called_once_with(
        prepare_java_tools.jar_path(prepare_java_tools.JAVA_TOOLS[1])
    )
