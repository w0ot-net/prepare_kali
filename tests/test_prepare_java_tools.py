import io
import json
import zipfile
from pathlib import Path
from unittest import mock

from prepare_debian.tasks import prepare_java_tools


def tool_spec(tmp_path: Path) -> prepare_java_tools.JavaToolSpec:
    return prepare_java_tools.JavaToolSpec(
        name="example",
        repository="owner/example",
        asset_pattern=r"example-all\.jar",
        jar_path=tmp_path / "example.jar",
        launcher_path=tmp_path / "bin" / "example",
    )


def jar_bytes() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
    return output.getvalue()


def test_latest_release_selects_matching_jar(tmp_path: Path) -> None:
    payload = {
        "tag_name": "v1.2.3",
        "assets": [
            {"name": "notes.txt", "browser_download_url": "https://example/notes"},
            {
                "name": "example-all.jar",
                "browser_download_url": "https://example/example.jar",
            },
        ],
    }
    with mock.patch.object(
        prepare_java_tools.urllib.request,
        "urlopen",
        return_value=io.BytesIO(json.dumps(payload).encode()),
    ):
        release = prepare_java_tools.latest_release(tool_spec(tmp_path))

    assert release == prepare_java_tools.Release(
        "v1.2.3", "https://example/example.jar"
    )


def test_install_release_is_atomic_and_idempotent(tmp_path: Path) -> None:
    spec = tool_spec(tmp_path)
    release = prepare_java_tools.Release("v1.2.3", "https://example/example.jar")
    with mock.patch.object(
        prepare_java_tools.urllib.request,
        "urlopen",
        return_value=io.BytesIO(jar_bytes()),
    ) as download:
        assert prepare_java_tools.install_release(spec, release) is True
        assert prepare_java_tools.install_release(spec, release) is True

    assert zipfile.is_zipfile(spec.jar_path)
    assert spec.jar_path.with_suffix(".jar.version").read_text() == "v1.2.3\n"
    download.assert_called_once()


def test_launcher_runs_jar_and_preserves_unmanaged_file(tmp_path: Path) -> None:
    spec = tool_spec(tmp_path)
    assert prepare_java_tools.ensure_launcher(spec) is True
    assert spec.launcher_path.read_text() == (
        "#!/bin/sh\n"
        "# Managed by prepare_debian.\n"
        f'exec java -jar "{spec.jar_path}" "$@"\n'
    )
    assert spec.launcher_path.stat().st_mode & 0o111

    spec.launcher_path.write_text("#!/bin/sh\necho custom\n")
    assert prepare_java_tools.ensure_launcher(spec) is False
    assert spec.launcher_path.read_text() == "#!/bin/sh\necho custom\n"


def test_main_requires_root() -> None:
    with (
        mock.patch.object(prepare_java_tools.os, "geteuid", return_value=1000),
        mock.patch.object(prepare_java_tools.apt_utils, "ensure_apt_package") as apt,
    ):
        assert prepare_java_tools.main() is False

    apt.assert_not_called()
