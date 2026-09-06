# 예제 스크립트

`krx_fundamentals_client` 스크레이퍼를 직접 호출하는 사용 예제 모음입니다.
서버는 없습니다 — 각 스크립트가 실행 시점에 DART/KRX/네이버 소스에 직접 요청합니다.

## 사전 준비

```bash
pip install krx-fundamentals-client
export DART_API_KEY=...   # https://opendart.fss.or.kr 에서 무료 발급
```

## 예제 목록

| 파일 | 설명 | 방식 |
|------|------|------|
| `basic_usage.py` | `DartScraper`/`NaverScraper`로 한 종목의 기업 개황·재무제표·투자지표·배당·대주주를 순서대로 조회 | 비동기 (`asyncio`) |
| `screening.py` | `KrxScraper`로 전 종목 투자지표를 받아 `screen_stocks`/`rank_stocks`로 가치주·배당주 스크리닝 및 랭킹 (KRX 경로 차단 시 빈 결과 — [`docs/krx-blocked.md`](../docs/krx-blocked.md) 참고) | 비동기 (`asyncio`) |
| `portfolio_analysis.py` | 여러 종목의 투자지표(네이버)·배당 이력(DART)을 병렬 수집해 요약 테이블과 포트폴리오 평균 계산 | 비동기 (`asyncio`) |

## 실행 방법

```bash
python examples/basic_usage.py
python examples/screening.py
python examples/portfolio_analysis.py
```
