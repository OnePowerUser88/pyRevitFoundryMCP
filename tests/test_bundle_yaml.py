"""Tests for BundleYamlAnalyzer."""

from pathlib import Path

from foundry_core.analyzers.bundle_yaml_analyzer import BundleYamlAnalyzer

FIXTURES = Path(__file__).parent / "fixtures" / "sample_extension"


def test_infers_title_from_script():
    analyzer = BundleYamlAnalyzer(FIXTURES)
    # Button2 has __title__ = "Button Two"
    inferred = analyzer.infer_bundle_yaml(
        "MyExt.extension/Tab1.tab/Panel1.panel/Button2.pushbutton",
        "Button2.pushbutton",
    )
    assert inferred["title"] == "Button Two"
    assert inferred["confidence"] == "high"


def test_generates_yaml_content():
    analyzer = BundleYamlAnalyzer(FIXTURES)
    inferred = {"title": "Test Tool", "tooltip": "Test"}
    content = analyzer.generate_yaml_content(inferred)
    assert "title:" in content
    assert "Test Tool" in content
    assert "tooltip:" in content
    assert "help_url:" in content
