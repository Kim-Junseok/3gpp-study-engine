# 개인 연구 웹앱 실행·검증

이 브랜치의 목표는 **A: 웹 기능 구현·검증**입니다. **B: 실제 corpus·실제 모델을
사용한 연구 보고서 수락**은 별도이며 아직 대기 상태입니다. A만 통과하면
“웹 기능 구현 완료, 실제 연구 검증 대기”로 보고합니다. 현재 실제 corpus와 canonical
`$CODEX_HOME/TECHNICAL_WRITING_STYLE.md`는 미제공이며 유료 호출은 비활성화되어 있습니다.

## 설치와 인증된 로컬 실행

Python 3.11 이상에서 기존 repository를 사용합니다. 개발 환경과 운영 서버는 별개입니다.
아래 명령은 서비스를 등록하거나 배포하지 않습니다.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev,web,web-test]'
mkdir -p work
umask 077
read -r -s -p '웹 접속 암호 (12자 이상): ' WEB_ACCESS_PASSWORD
printf '%s' "$WEB_ACCESS_PASSWORD" > work/web-access-password
unset WEB_ACCESS_PASSWORD
export THREEGPP_WEB_PASSWORD_FILE="$PWD/work/web-access-password"

# 실제 전달 자료가 없는 경우: 빈 자료 상태를 표시한다. 수집하지 않는다.
.venv/bin/python -m threegpp_web \
  --data-root "$PWD/var/research" --state-root "$PWD/var/web" --port 8765
```

같은 장치에서 `http://127.0.0.1:8765`를 엽니다. 원격 클라우드의 loopback 주소는
노트북·휴대폰에서 직접 열리는 주소가 아닙니다. 인증·HTTPS를 갖춘 미리보기나 운영
진입점을 확인한 뒤에만 외부 주소를 제공합니다. 현재 외부 미리보기·배포는 없습니다.
암호는 코드·명령행 인자·Git·로그에 넣지 않습니다. `THREEGPP_WEB_PASSWORD` 환경변수도
지원하지만 파일 secret을 권장합니다. `/work/`와 `/var/`는 Git에서 제외합니다.

단일 소유자 session은 HttpOnly/SameSite cookie와 CSRF로 보호하며 로그인 때 회전합니다.
현재 실패 제한은 session별 5회/분입니다. 외부 운영에서는 인증 프록시/OIDC 등과
전역 제한을 별도로 검증해야 하며, 현재 로컬 인증을 운영 인증 검증으로 표현하지 않습니다.
한 state 디렉터리에 서비스 프로세스 하나만 허용합니다. 여러 uvicorn worker를 쓰지 않습니다.

## 합성 fixture 실행

```bash
.venv/bin/python -m threegpp_web --fixture \
  --data-root "$PWD/var/fixture-corpus" \
  --state-root "$PWD/var/fixture-web" --port 8765
```

`--fixture`에는 명시적인 별도 data-root가 필요합니다. 실제 데이터가 들어 있는
디렉터리는 사용할 수 없습니다. 이 모드만 synthetic 원문과 네트워크 없는 인용 카드
작성기를 사용하며 모든 화면에 검증용임을 표시합니다. 예시 질문은 `FixtureTopic`을
확인하고 싶다는 내용으로 입력합니다. 범위는 RAN1, 125~125, 직접 원문 용어
`FixtureTopic`, 자료 기준은 “합성 fixture v1”로 지정합니다. 자료·용어 확인 후 명시적으로
승인·실행하면 3채널 출처와 fixture 결과 화면을 검증할 수 있습니다. 실제 연구로
수락하거나 기존 실제 Markdown 보고서를 검증한 것은 아닙니다.

## 자료와 운영 한도

실제 corpus의 필요한 디렉터리·용량 측정·전달·복원 명령은
[CORPUS_TRANSFER.md](CORPUS_TRANSFER.md)를 따릅니다. 노트북에 직접 접근할 수 있다고
가정하지 않습니다. 정규화된 원문을 읽는 데 proposition 준비·review는 필요 없습니다.

다음 환경변수는 **MVP 운영 한도**이며 엔진의 한계가 아닙니다.

| 변수 | 기본값 |
|---|---:|
| `THREEGPP_WEB_MAX_MEETINGS` | 3 |
| `THREEGPP_WEB_MAX_SOURCES` | 20 |
| `THREEGPP_WEB_MAX_INPUT_TOKENS` | 32768 |
| `THREEGPP_WEB_MAX_OUTPUT_TOKENS` | 8192 |
| `THREEGPP_WEB_TIMEOUT_SECONDS` | 180 |

Stage A 화면은 선택된 원문 구절·필요한 문맥·출처/질문 envelope의 UTF-8 byte 수를
보수적인 계획 지표로 사용합니다. 이를 특정 모델의 정확한 token 수라고 표현하지
않습니다. 실제 모델 연동 때는 instructions·schema를 포함한 전체 요청에 대해 선정
모델의 tokenizer로 계산해야 합니다. 상한 초과 시 내용을 몰래 잘라내지 않습니다.
기존 source reader의 구절·문맥 한도로 생기는 절단과 누락은 별도로 표시합니다.
실제 모델 timeout 집행은 아직 활성화하거나 실서비스에서 검증하지 않았습니다.

## 앱 상태 백업·새 환경 복원

서비스를 먼저 종료합니다. 백업 도구는 실행 lock이나 남은 SQLite journal이 있으면
거부합니다. 연구 corpus와 앱 상태는 별도로 전달합니다.

```bash
mkdir -p work/backup
.venv/bin/python -m threegpp_web.state_backup pack \
  --state-root "$PWD/var/web" --output "$PWD/work/backup/web-state-001.tar.gz"

# archive와 .sha256를 새 환경에 전달한 후, 존재하지 않는 새 경로에 복원한다.
.venv/bin/python -m threegpp_web.state_backup restore \
  --archive "$PWD/work/backup/web-state-001.tar.gz" \
  --destination "$PWD/var/restored-web-001"
```

백업에는 `app.sqlite3`와 결과·relative asset map을 포함합니다. 비밀번호·세션은 제외하며
복원 후 새 로그인 설정이 필요합니다. 별도로 복원한 corpus를 `--data-root`로 연결합니다.
pending/running 작업은 재시작 시 중단으로 표시하고 자동 재실행하지 않습니다.
기존 결과·출처 링크를 보존하며 실제 자료의 경로·checksum이 맞지 않으면 출처를 거부합니다.
사업자·도메인·정기 백업 일정은 배포 때 확정합니다.

## 재현 가능한 검증

```bash
mkdir -p work/review
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  .venv/bin/python scripts/check_web_offline.py -o addopts='' -q \
  --junitxml=work/review/python-tests.xml

# 이미 설치된 Chromium이 있으면 그 실행파일을 사용한다.
# 없으면 환경 정책에서 허용하는 공식 Playwright 설치를 별도로 수행한다.
.venv/bin/python scripts/check_web_browser.py \
  --chromium /usr/bin/chromium --output work/review/browser
```

첫 명령은 Internet socket을 차단한 기존+신규 Python 회귀 검사입니다. 모델 테스트는
MockTransport만 사용합니다. 두 번째 명령은 임시 인증 서버 2개(합성·빈 자료), 실제
Chromium, 360/390/1440px에서 화면 이동·주요 조작·넘침을 검사하고 캡처·JSON을 남깁니다.
외부 브라우저 요청은 차단하며 임시 서버는 종료합니다. 캡처의 연구 내용은 합성입니다.

## B 단계에서 별도로 확인할 사항

- 실제 corpus 용량·전달·원래 provenance·새 경로 복원 결과.
- canonical 문체 가이드 제공과 실제 확인.
- 모델명·현재 단가·가격 근거·모델별 tokenizer·예산 집행 방식·키·사용 승인.
- `threegpp_web.model`은 준비된 **비활성 adapter**이며 현재 웹 worker에 연결되지
  않습니다. API key를 설정하는 것만으로 활성화되지 않습니다. 승인 후 연결하고
  ledger는 반드시 `state_root/app.sqlite3`를 공유하여 백업에 비용 예약을 보존합니다.
- 모의 시험에서 인증 오류·429·timeout·응답 오류·예산 경쟁·불명확 호출 재시도 금지는
  검사하지만 실제 API 호환성·실제 단가·모델 품질을 확인한 것은 아닙니다.
- 실제 수락 보고서의 모든 주장에 대한 출처·locator 연결을 자동 확인합니다.
- **별도로**, 모든 기술 주장을 원문과 필요한 문맥에 대조하는 사람의 검토를
  제시합니다. 주체·조건·수치·모달리티·공동제출·3채널 권한·누락을 확인합니다.
  출처 링크 통과를 내용 정확성 통과라고 쓰지 않습니다.

main 반영·annotated tag·운영 배포는 최종 수락 후 저장소 절차로 진행합니다.
