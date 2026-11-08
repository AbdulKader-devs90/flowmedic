"""Empty exports and repository placeholders are not diagnostic evidence."""

from pathlib import Path

from mcp_servers.log_reader.server import LogReader


def test_discovery_skips_hidden_and_empty_files(tmp_path: Path) -> None:
    (tmp_path / ".gitkeep").write_text("placeholder", encoding="utf-8")
    (tmp_path / "empty.log").touch()
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "server.log").write_text("hidden", encoding="utf-8")
    nested = tmp_path / "exports"
    nested.mkdir()
    (nested / "server.log").write_text("ERROR sample", encoding="utf-8")
    result = LogReader([tmp_path]).list_files(str(tmp_path))
    assert [item["name"] for item in result["files"]] == [
        str(Path("exports/server.log"))
    ]
