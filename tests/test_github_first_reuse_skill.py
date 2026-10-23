"""Regression tests for the repository-local GitHub-first Codex skill."""
import importlib.util
import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/github-first-reuse/SKILL.md"
SCRIPT = ROOT / ".agents/skills/github-first-reuse/scripts/github_candidates.py"
AGENTS = ROOT / "AGENTS.md"


def _module():
    spec = importlib.util.spec_from_file_location("github_candidates", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_codex_skill_discoverable_and_safety_gates():
    content = SKILL.read_text(encoding="utf-8")
    assert content.startswith("---\nname: github-first-reuse\ndescription:")
    for required in ("GitHub", "LICENSE", "AGENTS.md", "docs/spec/", "测试", "不执行", "docs/oss-reuse/"):
        assert required in content
    assert (SKILL.parent / "references/reuse-decision-template.md").is_file()
    assert "github-first-reuse" in AGENTS.read_text(encoding="utf-8")


def test_search_url_encodes_query_and_filter():
    m = _module()
    query = parse_qs(urlsplit(m.build_url("pdf audio & parser", "Python", 8)).query)
    assert query["q"] == ["pdf audio & parser language:Python"]
    assert query["per_page"] == ["8"]
    with pytest.raises(ValueError):
        m.build_url(" ", None, 6)
    with pytest.raises(ValueError):
        m.build_url("ocr", None, 30)


def test_candidates_require_license_verification_and_no_network_in_tests(monkeypatch):
    m = _module()
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    class FakeResponse:
        def __enter__(self):
            return io.BytesIO(json.dumps({"items": [{"full_name": "owner/tool", "html_url": "https://github.com/owner/tool", "stargazers_count": 100}, {"bad": "entry"}]}).encode())
        def __exit__(self, *args):
            return False
    def fake_opener(request, timeout):
        assert timeout == 15
        assert request.full_url.startswith("https://api.github.com/search/repositories?")
        assert "Authorization" not in request.headers
        return FakeResponse()
    found = m.search("pdf parser", limit=2, opener=fake_opener)
    assert len(found) == 1
    assert found[0]["repo"] == "owner/tool"
    assert "UNVERIFIED" in found[0]["license"]
