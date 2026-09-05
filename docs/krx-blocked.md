# KRX 수집 경로 차단 — 코드 추적 (2026-08 실측)

## 무슨 일이 일어나는가

KRX 정보데이터시스템이 MDCSTAT 계열에 회원 로그인을 걸면서, OTP 발급
(`comm/fileDn/GenerateOTP/generate.cmd`)이 토큰 대신 문자열 `LOGOUT` 을 돌려준다.

[`KrxScraper._get_otp`](../src/krx_fundamentals_client/scrapers/krx.py) 는 응답이 비었는지와
500자를 넘는지만 검사한다. `LOGOUT` 은 6자라 이 검사를 통과하고, 정상 OTP 로 간주돼 그대로
다운로드 단계로 넘어간다. 다운로드는 빈 CSV 를 받고 파서는 **예외 없이 빈 리스트를 반환**한다.

```python
otp = resp.text.strip()
if not otp or len(otp) > 500:
    raise ValueError(f"Unexpected OTP response (len={len(otp)})")
return otp
```

## 왜 조용히 넘어가는가

호출자 입장에서는 예외가 없으니 정상 호출처럼 보인다 — `KrxScraper.fetch_investment_ratios()`
같은 메서드가 그냥 빈 리스트를 반환할 뿐이다. 라이브러리는 상태를 별도로 기록하지 않으므로,
**빈 결과와 "일시적으로 아무 종목도 없는 정상 상태"를 호출자가 구분할 방법이 없다** — 반환된
리스트가 비어 있으면 KRX 경로가 막혔을 가능성을 의심해야 한다.

## 영향 범위

- **빈다**: KRX 가 채우기로 되어 있는 투자지표(PER/PBR/배당수익률)·시가총액·섹터.
  `screen_stocks`/`rank_stocks`에 넘길 `InvestmentRatio` 목록도 함께 빈다.
- **부분 복구**: 상위 100종목 한정으로 `NaverScraper`가 대체 수집 가능.
- **영향 없음**: DART 경로(기업개황·재무제표·배당) — `DartScraper`는 이 문제와 무관하다.
