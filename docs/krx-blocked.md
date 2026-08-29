# KRX 수집 경로 차단 — 코드 추적 (2026-08 실측)

## 무슨 일이 일어나는가

KRX 정보데이터시스템이 MDCSTAT 계열에 회원 로그인을 걸면서, OTP 발급
(`comm/fileDn/GenerateOTP/generate.cmd`)이 토큰 대신 문자열 `LOGOUT` 을 돌려준다.

[`KrxScraper._get_otp`](../src/krx_fundamentals_api/scrapers/krx.py) 는 응답이 비었는지와
500자를 넘는지만 검사한다. `LOGOUT` 은 6자라 이 검사를 통과하고, 정상 OTP 로 간주돼 그대로
다운로드 단계로 넘어간다. 다운로드는 빈 CSV 를 받고 파서는 **예외 없이 빈 리스트를 반환**한다.

```python
otp = resp.text.strip()
if not otp or len(otp) > 500:
    raise ValueError(f"Unexpected OTP response (len={len(otp)})")
return otp
```

## 왜 초록불로 남는가

`crawl_krx_ratios` 는 예외가 나지 않았으니 성공으로 기록한다 —
`update_crawler_status(DataSource.KRX, "ratios", len(all_ratios))` 를 `error` 없이 부르고
([`services/scheduler.py`](../src/krx_fundamentals_api/services/scheduler.py)),
상태 판정은 `is_healthy = error is None` 이다
([`services/cache.py`](../src/krx_fundamentals_api/services/cache.py)).

그래서 `/api/v1/status` 에 `items_count: 0` 이면서 `is_healthy: true` 인 행이 남는다.
**0건 수집이 초록불로 기록되는 조용한 실패**다.

## 영향 범위

- **빈다**: KRX 가 채우기로 되어 있는 투자지표(PER/PBR/배당수익률)·시가총액·섹터.
  여기에 얹힌 `/ranking`·`/screening`·`/market/sectors` 도 함께 빈다.
- **부분 복구**: 상위 100종목 한정으로 네이버 보조 수집이 `ratio:all` 을 채워 넣는다.
- **영향 없음**: DART 경로(기업개황·재무제표·배당).
