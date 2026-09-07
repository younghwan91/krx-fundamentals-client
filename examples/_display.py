"""예제 스크립트 공용 콘솔 출력 헬퍼."""

from __future__ import annotations

import os
import sys


def print_header(title: str, width: int = 72) -> None:
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def print_table(headers: list[str], rows: list[list[str]], widths: list[int]) -> None:
    header_line = " | ".join(h.center(w) for h, w in zip(headers, widths))
    separator = "-+-".join("-" * w for w in widths)
    print(f"  {header_line}")
    print(f"  {separator}")
    for row in rows:
        line = " | ".join(
            str(v).rjust(w) if i > 0 else str(v).ljust(w)
            for i, (v, w) in enumerate(zip(row, widths))
        )
        print(f"  {line}")


def fmt(value: float | None, suffix: str = "", decimal: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:,.{decimal}f}{suffix}"


def require_dart_api_key() -> str:
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        print("❌ DART_API_KEY 환경변수를 설정하세요 (https://opendart.fss.or.kr)")
        sys.exit(1)
    return api_key
