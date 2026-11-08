# 준비된 연구 자료 전달·복원

이 절차는 **이미 준비된 자료의 사본을 전달**합니다. 자료 수집, 원문 다운로드,
새 연구 corpus 생성, DB migration, 재정규화, 추출, review 생성은 수행하지 않습니다.
개발 환경에서 노트북을 직접 볼 수 있다고 가정하지 않습니다. 아래 노트북 명령은
자료 소유자가 해당 장치에서 실행합니다.

웹 기능의 A 단계와 실제 연구 보고서의 B 단계는 별도입니다. 전송 checksum이 맞아도
한국어 보고서의 기술 주장·조건·문맥·출처 권한이 정확하다는 뜻은 아닙니다.

## 전달 단위와 필요한 파일

`THREEGPP_DATA_ROOT`로 사용하던 **하나의 일관된 데이터 디렉터리**를 선택합니다.
웹앱 소스나 노트북 홈 전체를 묶지 않습니다.

| 경로 | 전달 이유 | 누락 시 처리 |
|---|---|---|
| `metadata.duckdb` | 기존 메타데이터, 원문 receipt, snapshot 조회 | 실행에 필요한 DB 부재. 도구가 빈 DB를 만들지 않음 |
| `raw/` | 보존한 원문·공식 목록·회의 자료·Chair Note 바이트 | 원문·원래 receipt checksum 검증 실패 또는 자료 누락 |
| `normalized/` | 검증 가능한 원문 block과 메타데이터 snapshot | 읽기 불가. 자동 재정규화하지 않음 |
| `manifests/` | 원문 URL·발견/획득 시각·checksum·파생 자료 참조 | 원본이 불충분한 항목으로 보고. 임의 metadata 생성 금지 |
| `derived/topics/` | 기존 용어 결정과 profile revision | 명시적인 로컬 bootstrap·용어 검토 필요 |
| 기존 `derived/`의 나머지 자료 | 이미 있는 evidence·link·기타 이력 보존 | 선택된 보고서 경로에서 필요한 자료의 상태를 별도 확인 |

`raw/chair-notes/`, `normalized/chair-notes/`, `manifests/chair-notes/` 등은 위 디렉터리
아래에 포함됩니다. 회사 기고·선택한 Chair Note·공식 회의 결과는 독립 채널입니다.
Chair Note나 결과 자료가 없다고 읽을 수 있는 기고를 없던 것으로 처리하지 않습니다.
`verify`의 “prepared”는 읽을 수 있는 원문과 유효한 profile이 있다는 뜻이며,
세 채널의 완전성이나 B 단계 수락을 뜻하지 않습니다.

도구는 위 네 디렉터리와 `metadata.duckdb`만 선택합니다. 합성 fixture인 경우에는
`SYNTHETIC-FIXTURE-ONLY.txt` 표식도 반드시 그대로 전달합니다. 루트의 `.env`, 자격 증명,
`.git`, `.venv`, 기존 보고서 및 별도 앱 상태 DB는 포함하지 않습니다. 자료 디렉터리
안에도 API 키나 자격 증명을 보관하지 마십시오. 자료 내의 기존 source text와 review
기록은 바꾸지 않으며, 기록이 있다는 이유로 실제 사람의 수락이라고 인증하지 않습니다.

## 용량 확인과 노트북에서의 묶기

먼저 자료를 쓰는 CLI·앱·worker를 종료하고 DB 연결을 닫습니다. DuckDB WAL이 있으면
도구가 거부합니다. DB와 파일이 동시에 변경되는 동안의 사본은 사용하지 않습니다.
읽기 전용 검증도 원문 파일 전체를 checksum 계산하므로 자료 크기에 따라 시간이 듭니다.

아래 예시는 POSIX shell입니다. `SOURCE_CORPUS`만 실제 로컬 데이터 경로로 바꿉니다.
노트북에는 이 브랜치의 코드와 기존 Python 의존성이 필요하며 Python 3.11 이상을 사용합니다.

```bash
cd /path/to/3gpp-study-engine
SOURCE_CORPUS='/path/to/existing/3gpp-data'
mkdir -p work/handoff

# 파일별 bytes·SHA-256, 구성요소별 bytes, 총량을 확인한다.
PYTHONPATH=src python -m threegpp_web.corpus inspect \
  --data-root "$SOURCE_CORPUS" > work/handoff/inventory.json

# 선택 사항: 디스크의 실제 사용량과 남은 공간도 확인한다.
du -sh "$SOURCE_CORPUS"
df -h work/handoff

# 원래 receipt, 원문, 정규화 block, profile·기존 manifest를 읽기 전용 검증한다.
PYTHONPATH=src python -m threegpp_web.corpus verify \
  --data-root "$SOURCE_CORPUS" > work/handoff/source-verification.json

# 새 파일명에 패키징한다. 기존 archive/sidecar를 덮어쓰지 않는다.
PYTHONPATH=src python -m threegpp_web.corpus pack \
  --data-root "$SOURCE_CORPUS" \
  --output "$PWD/work/handoff/prepared-corpus-001.tar.gz" \
  > work/handoff/pack-result.json
```

`verify`는 연구 입력이 불충분하거나 손상되었으면 exit code 2를 반환합니다. 예를 들어
profile만 없으면 `needs_data`로 표시하며, 기존 원문은 pack할 수 있습니다. checksum
충돌·외부 경로 의존·지원하지 않는 DB schema는 `blocked`입니다. 오류를 자동으로
수정하거나 profile을 생성하지 않습니다. **서로 다른 실행의 DB와 원문 폴더를 섞어서
오류를 덮지 않습니다.** 전달 전 오류와 누락 목록을 같이 검토합니다.

생성되는 파일은 다음과 같습니다.

- `prepared-corpus-001.tar.gz`: 원본 파일과 내부 `TRANSFER_MANIFEST.json`.
- `prepared-corpus-001.tar.gz.sha256`: 전송 archive checksum.
- `prepared-corpus-001.tar.gz.manifest.json`: 파일별 경로·크기·checksum을 검토할 외부 사본.
- `inventory.json`, `source-verification.json`, `pack-result.json`: 전달 전 상태·용량 확인 기록.

archive는 압축률을 보장하지 않습니다. 도구의 `recommended_free_bytes`는
**원본 총 bytes의 2배 + 64 MiB**인 보수적인 계획 값입니다. 클라우드 복원 시에는
이미 올린 archive 외에 풀린 자료 크기와 staging 여유가 필요합니다. 운영자가 대상
디스크의 여유를 확인해야 하며, 도구가 용량을 자동 증설하지 않습니다.

전송 도구의 기본 guardrail은 파일 100,000개, 파일당 4 GiB, 전체 20 GiB,
개별 정규화 gzip의 펼친 내용 128 MiB입니다. 엔진의 한계가 아닙니다. 용량 조사 결과에
따라 `--max-files`, `--max-file-bytes`, `--max-bytes`, `--max-normalized-bytes`로 변경하며,
동일하거나 더 큰 허용값을 pack과 restore에 사용합니다. 최대 3회의·20문서 같은 웹
MVP 운영 한도와도 별개입니다.

## 클라우드로 전달

사용자가 승인한 파일 전달 경로로 archive·`.sha256`·외부 manifest·검증 기록을 함께
전달합니다. 예를 들어 채팅의 파일 첨부나 사용자가 고른 저장 서비스의 다운로드를
사용할 수 있습니다. 사업자·도메인·정기 백업 일정은 배포 단계에서 정합니다.
도구는 Drive나 노트북으로 접속하지 않으며, 다운로드 URL이나 새 3GPP 요청을 만들지
않습니다. 실제 첨부가 도착한 후에야 클라우드의 로컬 archive 경로를 알 수 있습니다.

코드 저장소가 연결되어 있다는 사실은 위 자료가 전달되었다는 뜻이 아닙니다.
이번 개발 환경에는 실제 원문·연구 DB·주제 profile이 아직 제공되지 않았습니다.

## 새 클라우드 경로로 복원

복원은 Linux의 원자적 `renameat2(RENAME_NOREPLACE)`를 사용합니다. 검사 중에는
임시 staging만 존재하고, 전송·원문 검증을 마친 디렉터리를 새 목적지에 한 번에
게시합니다. 이미 존재하는 목적지와 archive member의 경로 이탈·중복·링크·초과 크기를
거부합니다. PAX/GNU 확장 헤더도 내부 읽기 전에 64 KiB·연속 16개로 제한합니다.
DB는 외부 파일·URL 읽기와 확장 자동 설치를 끄고 필요한 이름이 실제 BASE TABLE인지
확인합니다. 일반 `tar -x`로 원래 corpus 위에 풀지 않습니다.

```bash
cd /workspace/work/0.14.0-personal-web
INCOMING_ARCHIVE='/workspace/work/incoming/prepared-corpus-001.tar.gz'
RESTORED_CORPUS='/workspace/work/runtime/research-001'

# 별도로 전달받은 checksum도 확인한다.
(cd "$(dirname "$INCOMING_ARCHIVE")" && sha256sum -c "$(basename "$INCOMING_ARCHIVE").sha256")

# RESTORED_CORPUS는 아직 존재하지 않아야 한다.
PYTHONPATH=src python -m threegpp_web.corpus restore \
  --archive "$INCOMING_ARCHIVE" \
  --destination "$RESTORED_CORPUS" \
  > /workspace/work/handoff-restore-result.json

PYTHONPATH=src python -m threegpp_web.corpus verify \
  --data-root "$RESTORED_CORPUS" \
  > /workspace/work/handoff-restored-verification.json

# 검증과 앱 설정 확인 후 해당 corpus를 읽기 경로로 지정한다.
export THREEGPP_DATA_ROOT="$RESTORED_CORPUS"
```

archive 옆 `.sha256`가 있으면 restore가 자동 검증합니다. 별도 채널에서 확인한 SHA가
있으면 `--expected-sha256 <64자리 값>`으로 지정할 수도 있습니다. sidecar가 없다면
파일별 내부 manifest는 검증하지만 archive 전체 checksum을 별도 확인했다고 보고하지
않습니다. checksum 자체가 신뢰할 원문·권한을 증명하는 서명인 것은 아닙니다.

복원은 원래 URL·발견 시각·획득 시각·hash·receipt를 고치지 않습니다. TDoc 원문은 기존
core가 지원하는 `raw/tdocs/<wg>/<meeting>/<tdoc>/<filename>` 경로에서 찾습니다.
노트북의 절대 `raw.local_path`는 provenance로 그대로 남기되, 클라우드에서 그 경로를
따라 외부 파일을 읽지 않습니다. 정규화 파일이나 receipt가 외부 절대 경로에 의존하면
오류로 보고합니다. 수동 문자열 치환이나 가짜 경로 작성으로 통과시키지 않습니다.

검증은 다음을 구분합니다.

1. **전송 무결성:** archive와 개별 파일이 전달본 manifest와 같은가.
2. **기존 provenance와 읽기 가능성:** DB를 읽기 전용으로 열 수 있는가. 원문 bytes,
   checksum, 정규화 identity·block, profile과 참조 manifest가 기존 기록과 맞는가.
3. **보고서의 출처 연결:** 실제 선택 범위에서 주장별 인용이 읽은 원문·locator로 연결되는가.
4. **내용의 정확성:** B 단계 실제 보고서의 모든 기술 주장을 원문·필요 문맥과 사람이
   대조했는가. 조건·수치·권한·누락을 올바르게 표현했는가.

1과 2의 자동 통과는 3과 4의 수락을 대신하지 않습니다. 전체 회의 자료를 확보했거나,
회사 제안이 합의되었다거나, human review가 있었다고 추론하지 않습니다. 모델 API는
모델명·단가·예산 집행 방식·키·사용 승인이 갖춰질 때까지 비활성화합니다.

## 앱 상태 복원과 배포 결정

연구 corpus 전송은 질문·승인 scope·작업·보고서가 든 앱 상태 백업과 별개입니다.
새 환경에서 질문 이력을 이어가려면 **worker를 중단한 일관된 앱 상태 사본**도 별도로
전달해야 합니다. SQLite DB만 실행 중 복사하지 말고 앱의 snapshot/backup 절차를
사용합니다. corpus archive에 앱 키나 세션 secret을 넣지 않습니다.

A 단계에서는 합성 fixture를 다른 새 디렉터리로 복원하여 원문·receipt·이력 경계를
시험합니다. 실제 corpus가 전달되면 같은 복원 절차를 다시 실행하고, 실제 모델로
작성한 보고서의 자동 검사와 사람 검토를 별도 기록합니다. 운영 사업자·인증 제공자·
도메인·정기 백업 일정은 배포 수락 때 확정하며, 미정이어도 A 단계 개발은 진행합니다.

## Canonical 기술 문체 가이드

canonical guide는 **`$CODEX_HOME/TECHNICAL_WRITING_STYLE.md`**입니다. 현재 클라우드의
`CODEX_HOME=/home/agent/.codex`에서 해당 파일은 **미제공**입니다. 보고서 가이드와
용어 문서는 별도 지침이며 이 canonical guide를 읽었다고 기록하지 않습니다.

자료 소유자는 canonical 파일 하나를 첨부하거나 승인된 전달 경로로 보내면 됩니다.
`CODEX_HOME` 전체를 묶지 않습니다. 전달 후 checksum과 실제 내용을 확인하고 제공된
문서를 작업 지침으로 읽습니다. 클라우드의 canonical 경로에 놓을 수 없으면 허용된
작업 폴더의 사본 경로와 제공 사실을 명시하여 참조합니다. 가이드가 없다는 사실은
A 단계 독립 개발을 막지 않지만, 최종 문체 검토의 미확인 항목으로 남습니다.
