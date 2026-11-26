# Changelog

## 0.2.0 — 2026-11-27

첫 PyPI 배포입니다.

### 추가
- `krx-fundamentals` CLI: API 키 없이 종목명이나 6자리 코드로 투자지표(현재가·시가총액·PER·PBR·EPS·BPS·배당수익률·외국인소진율·52주 위치)를 나란히 비교합니다. `--sort per|pbr|dividend|cap`, `--json`.
- `NaverScraper.search(name)`: 종목명으로 `(종목코드, 종목명, Market)` 목록을 찾습니다.

### 고침
- `screen_stocks(market=...)`가 대소문자·`Market` enum을 받습니다. 지원하지 않는 시장은 `ValueError`, 시장 필터를 쓰면 시장 정보가 없는 종목은 뺍니다 (#17, @sogav21).
- DART 발행주식수: 보통주 라벨 표기 변형과 "의결권이 있는 주식" 표기를 받고, 애매하면 값을 버립니다.
- DART 배당·네이버 투자지표가 `None`으로만 오던 문제.

## 0.1.0

FastAPI 서버를 걷어내고 클라이언트 라이브러리로 바꾼 첫 버전입니다 (PyPI 미배포).
