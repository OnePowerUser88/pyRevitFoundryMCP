"""Tests for RepoIndexer."""

from pathlib import Path

from foundry_core.indexers.repo_indexer import RepoIndexer

FIXTURES = Path(__file__).parent / "fixtures" / "sample_extension"


def test_repo_indexer_parses_bundles():
    idx = RepoIndexer(FIXTURES).scan()
    assert "extensions" in idx
    assert len(idx["extensions"]) >= 1
    bundles = idx.get("bundles", [])
    assert any(b["name"] == "Button1.pushbutton" for b in bundles)
    assert any(b["name"] == "Button2.pushbutton" for b in bundles)
    btn1 = next(b for b in bundles if b["name"] == "Button1.pushbutton")
    assert btn1.get("bundle_yaml") is True
    btn2 = next(b for b in bundles if b["name"] == "Button2.pushbutton")
    assert btn2.get("bundle_yaml") is not True
