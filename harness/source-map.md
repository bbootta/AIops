# 소스 맵

에이전트가 참조하는 취약점 정보 소스. 1차 소스를 우선한다.

## 취약점 데이터베이스

| 소스 | URL | 용도 |
|---|---|---|
| NVD | https://nvd.nist.gov | CVE 상세, CVSS 점수 |
| CISA KEV | https://www.cisa.gov/known-exploited-vulnerabilities-catalog | 실제 악용 관측 취약점 |
| OSV | https://osv.dev | 오픈소스 패키지 취약점 (생태계별) |
| GitHub Advisory | https://github.com/advisories | GHSA, 패키지 취약점 |
| EPSS | https://www.first.org/epss/ | 악용 확률 점수 |

## 국내 권고

| 소스 | URL | 용도 |
|---|---|---|
| KISA 보호나라 | https://www.boho.or.kr | 국내 보안 공지·권고 |
| KrCERT | https://www.krcert.or.kr | 침해사고 대응, 취약점 공지 |

## 해외 CERT / 기관

| 소스 | URL | 용도 |
|---|---|---|
| CISA Advisories | https://www.cisa.gov/news-events/cybersecurity-advisories | 미국 권고 |
| JPCERT/CC | https://www.jpcert.or.jp | 일본 권고 (아시아권 위협 동향) |

## 주요 벤더 보안 공지

자산 목록(`templates/asset-inventory.md`)에 등재된 벤더 기준으로 유지한다.
아래는 초기 목록이며 자산에 맞게 조정한다.

| 벤더 | URL |
|---|---|
| Ubuntu (USN) | https://ubuntu.com/security/notices |
| Debian (DSA) | https://www.debian.org/security/ |
| Apple | https://support.apple.com/ko-kr/HT201222 |
| Microsoft (MSRC) | https://msrc.microsoft.com/update-guide |
| Node.js | https://nodejs.org/en/blog/vulnerability |
| Python (PSF) | https://mail.python.org/archives/list/security-announce@python.org/ |
| Docker | https://docs.docker.com/security/security-announcements/ |
| AWS | https://aws.amazon.com/security/security-bulletins/ |
| Slack / Salesforce | https://slack.com/security · https://status.slack.com |

## 공개 인증서 투명성 로그

| 소스 | URL | 용도 |
|---|---|---|
| crt.sh | https://crt.sh | 자사 도메인 서브도메인 확인 |

## 사용 규칙

- 발견 사항 인용 시 소스 URL과 확인 일자를 기록한다.
- 뉴스·블로그는 참고용이며, 발견 근거로는 위 1차 소스를 사용한다.
- 자산 변경 시 벤더 공지 목록을 함께 갱신한다.
