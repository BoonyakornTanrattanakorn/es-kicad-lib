import json
import zipfile
from pathlib import Path

from generator.package_tools import create_zip_archive, update_version


def test_update_version_replaces_versions_array(tmp_path):
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps({"name": "x", "versions": [{"version": "old", "status": "stable", "kicad_version": "7.0"}]}),
        encoding="utf-8",
    )

    update_version(str(metadata_path), "2026.08.09", kicad_version="8.0", status="stable")

    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert data["versions"] == [{"version": "2026.08.09", "status": "stable", "kicad_version": "8.0"}]


def test_create_zip_archive_uses_relative_paths_not_absolute(tmp_path, monkeypatch):
    (tmp_path / "symbols").mkdir()
    (tmp_path / "symbols" / "ES-Resistors.kicad_sym").write_text("x" * 200, encoding="utf-8")
    (tmp_path / "metadata.json").write_text("y" * 200, encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    output_zip = tmp_path / "out.zip"
    create_zip_archive(str(output_zip), ["symbols", "metadata.json"])

    names = zipfile.ZipFile(output_zip).namelist()
    assert "metadata.json" in names
    assert any(n.replace("\\", "/") == "symbols/ES-Resistors.kicad_sym" for n in names)
    assert not any(str(tmp_path).lstrip("/") in n for n in names)


def test_create_zip_archive_excludes_small_files(tmp_path, monkeypatch):
    (tmp_path / "tiny.kicad_sym").write_text("x", encoding="utf-8")  # under min_size_bytes
    (tmp_path / "real.kicad_sym").write_text("x" * 200, encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    output_zip = tmp_path / "out.zip"
    create_zip_archive(str(output_zip), ["tiny.kicad_sym", "real.kicad_sym"], min_size_bytes=128)

    names = zipfile.ZipFile(output_zip).namelist()
    assert "real.kicad_sym" in names
    assert "tiny.kicad_sym" not in names
