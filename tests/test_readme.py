"""README 예제 코드가 최소한 문법·import 이름은 맞는지 확인한다 (네트워크 호출 없음)."""

import ast
import re
from pathlib import Path

import pytest

import krx_fundamentals_client

ROOT = Path(__file__).resolve().parent.parent
BLOCK = re.compile(r"```python\n(.*?)```", re.S)


def _blocks() -> list[tuple[str, str]]:
    out = []
    for name in ("README.md", "README.en.md", "docs/guide.md"):
        for i, code in enumerate(BLOCK.findall((ROOT / name).read_text(encoding="utf-8"))):
            out.append((f"{name}#{i}", code))
    return out


@pytest.mark.parametrize(("where", "code"), _blocks(), ids=[w for w, _ in _blocks()])
def test_readme_block_compiles_and_imports_exist(where: str, code: str) -> None:
    tree = ast.parse(code, filename=where)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "krx_fundamentals_client":
            for alias in node.names:
                assert hasattr(krx_fundamentals_client, alias.name), f"{where}: {alias.name}"


def test_pypi_readme_has_no_relative_links() -> None:
    """PyPI 페이지는 레포 밖이다. pyproject 의 치환을 적용하면 상대 경로가 남지 않아야 한다."""
    import tomllib

    hook = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["hatch"]["metadata"][
        "hooks"
    ]["fancy-pypi-readme"]
    text = "".join((ROOT / f["path"]).read_text(encoding="utf-8") for f in hook["fragments"])
    for sub in hook["substitutions"]:
        text = re.sub(sub["pattern"], sub["replacement"], text)
    refs = re.findall(r'(?:src|srcset|href)="([^"]+)"|\]\(([^)]+)\)', text)
    relative = [a or b for a, b in refs if not re.match(r"https?://|#", a or b)]
    assert relative == []
