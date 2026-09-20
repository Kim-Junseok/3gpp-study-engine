# Fast-ARQ 회사별 Contribution 주장 정리

## 1. 범위와 읽는 방법

현재 로컬 자료에서 연구자가 승인한 Fast-ARQ proposition을 대상으로, 각 contribution이 제안·관찰·결론으로 제시한 내용을 기술 항목별로 정리한다. 범위는 RAN1 #125–#126의 승인된 10개 proposition, 6개 TDoc이다. 조직 메타데이터는 6개 이름(vivo, CATT, OPPO, Huawei, HiSilicon, Samsung)이며, Huawei·HiSilicon 공동 저자 집합을 한 묶음으로 보면 5개 조직 집합이다. 회사 전체의 공식 입장이나 회의 합의를 설명하는 보고서가 아니다.

자료를 `TopicTerminologyProfile → direct TDoc inventory → 현재 유효한 CONTRIBUTION SemanticEvidence → V0.12 AcceptedProposition → V0.13 reviewed PropositionRelation` 순서로 확인했다. DB는 읽기 전용으로 연결했다. 프로필·inventory identity와 상위 proposition 및 relation의 freshness 검증을 통과한 자료만 사용했다. 작성 기준 Git HEAD: `a0c802082d78321d19392f4c36d013643a19863a`.

- Topic profile: `topic-profile-e0e7f5ed87ddc3618136922d8239009f69bb8847cb53f3560713185902ec302d`
- Direct inventory: `topic-inventory-9d8392da696c820e176a8279544b8efb34022250d581f47b22861c24f2a7a6c1`
- V0.12 corpus: `topic-proposition-corpus-bb963771ac1e03deaff0345bc72bb86ae052d016f5a670c5c94c1676f79cdd43`
- V0.13 corpus: `proposition-relation-corpus-d3ea80f8d89034f51a799f73e6af829f1654c91bb88fa4da01c8b9bdda8bc116`

직접 검색에 사용된 승인 범위는 `Fast-ARQ` (user_seed), `Fast ARQ` (exact_variant)이다. 추가 `accepted_source_term`은 없다. 관찰된 source candidate와 related-only 표현은 직접 corpus에 추가하지 않았다. 아래 기술 항목 제목은 승인 문장을 읽기 위한 보고서 편집 항목이며, 엔진 ontology나 새 topic term으로 저장하지 않았다.

현재 direct inventory에는 중복 제거 후 8개 TDoc이 있고, 그중 8개가 content inspected 상태다. V0.12에는 SourceUnit 45개와 candidate 49개가 있으며, 본문은 AcceptedProposition 10개만 사용한다. SemanticEvidence가 있어도 아직 승인된 proposition이 없는 TDoc은 기술 주장 표에 넣지 않았다. 따라서 이 보고서가 직접 inventory의 모든 주장이나 Fast-ARQ 전체를 포괄하지는 않는다.

| Direct TDoc | 조직 메타데이터 | Meeting | Content inspected | 본문 사용 |
| --- | --- | --- | --- | --- |
| R1-2603486 | RAN2, MediaTek | 125 | True | 승인 proposition 없음; 내용 주장 제외 |
| R1-2603619 | vivo | 125 | True | 승인 proposition 있음 |
| R1-2603887 | CATT | 125 | True | 승인 proposition 있음 |
| R1-2604096 | OPPO | 125 | True | 승인 proposition 있음 |
| R1-2604142 | Samsung | 125 | True | 승인 proposition 있음 |
| R1-2604801 | ZTE Corporation, Sanechips | 125 | True | 승인 proposition 없음; 내용 주장 제외 |
| R1-2604921 | Huawei, HiSilicon | 125 | True | 승인 proposition 있음 |
| R1-2605792 | Samsung | 126 | True | 승인 proposition 있음 |

`P01`–`P10`은 이 문서의 읽기용 표식이다. 각 표식은 §5.2의 실제 AcceptedProposition ID, SemanticEvidence ID, 정확한 전체 문장, EvidenceRef와 연결된다. PROPOSAL은 제안, OBSERVATION은 관찰, CONCLUSION은 해당 contribution의 결론이다. 원문에 “Option”이 있어도 저장된 CONCLUSION을 PROPOSAL로 바꾸지 않았다.

원문을 직접 확인하는 순서는 다음과 같다.

1. 사람이 원 contribution을 읽으려면 raw DOCX/PDF/member가 우선이다. 이 보고서의 원본은 로컬 ZIP 안의 DOCX member로 확인했다. §5.1의 ZIP과 정확한 member 이름으로 열 수 있다. 별도 DOCX 파일이 추출되어 있다고 가정하지 않는다.
2. 정확한 근거 block을 찾으려면 normalized artifact와 EvidenceRef의 member·block ID를 사용한다.
3. 비교 단위를 확인하려면 AcceptedProposition의 전체 segment와 source span을 확인한다.
4. proposition 간 reviewed comparison을 확인하려면 V0.13 relation artifact의 양측 proposition, basis, review ID를 확인한다.

## 2. 핵심 기술 쟁점 요약

| Technical item | 본문 근거 | 읽을 때 유지할 범위 |
| --- | --- | --- |
| 상태 indication 선택 | [P03](#p03) | NACK-only 또는 ACK/NACK 선택을 설계에 맡길 수 있다는 OBSERVATION |
| UL trigger와 DCI 전달 방식 | [P01](#p01), [P07](#p07), [P06](#p06), [P09](#p09) | 특정 process failure, UL scheduling DCI, 여러 PUSCH/process용 dedicated DCI의 원문 세부사항 유지 |
| HARQ-ACK 신뢰도 | [P02](#p02), [P05](#p05) | 5G NR 기준선 재사용 가능성과 0.1% 오류율 제안을 각각 보존 |
| N2A 오류 검출·보고 | [P04](#p04) | L1/L2 및 6GR에서 연구하자는 제안 |
| failure 발생 빈도 | [P08](#p08), [P10](#p10) | under typical conditions 조건이 붙은 OBSERVATION |

## 3. Technical Item별 분석

### 3.1 HARQ process-status indication: NACK-only와 ACK/NACK 선택

#### 기술 질문

HARQ process 상태를 NACK만으로 알릴 것인가, 명시적 ACK/NACK으로 알릴 것인가?

#### 회사별 Contribution

| 회사/조직 | TDoc | Evidence Kind | 한글 요약 | 핵심 원문 | EvidenceRef |
| --- | --- | --- | --- | --- | --- |
| CATT | R1-2603887 / RAN1 #125 | OBSERVATION / CONTRIBUTION | CATT의 R1-2603887에서는 HARQ process-status indication을 NACK만 통지할지, 명시적 ACK/NACK을 모두 통지할지의 선택을 signaling 설계에 맡길 수 있다고 관찰로 제시한다. 하나의 방식을 확정한 제안으로 바꾸지 않는다. [P03](#p03) | “choose either only indicating HARQ NACK or supporting explicit ACK/NACK indication.” | RAN1 / 125 / R1-2603887 / `R1-2603887.docx` / `b000029` |

#### 검토된 Proposition Relation

아래는 기존 연구자 검토 결과다. 양측 표식은 전체 원문과 실제 proposition ID로 연결된다. 항목을 가로지르는 pair도 원래의 양측 단위를 그대로 표시했다.

| 양측 정확한 proposition | 기존 reviewed relation | Pair / Review / Accepted relation |
| --- | --- | --- |
| [P03](#p03) ↔ [P07](#p07) | OVERLAPPING | `proposition-pair-30380788fa0618064f417dd734c867753798da008c17fa071bf97a3a942fca40`<br>`proposition-relation-review-c72dcdbc0a14dca65ca098a87cd1e85d1d35645b280789ce8402fccc3679fa15`<br>`accepted-proposition-relation-f02494143ff901453986472978e86e7296b7344ee1c33c1902c747ad6fc5282a` |
| [P03](#p03) ↔ [P01](#p01) | OVERLAPPING | `proposition-pair-459f0169dd0b37df37143b23922c776c7af28404444c0fb26cd4f82e3ea0a5fe`<br>`proposition-relation-review-5e1b15357d7f66b9a75b580505bba40cb745c2b2ae31d088ebd596eeecaa5d40`<br>`accepted-proposition-relation-4c5055481cb7b2b64e4f8e2a073ab77ff3960d282dc1bd9be164bd030cae9cb8` |

모든 행의 authority는 `RESEARCHER_ANALYSIS`이며, basis는 링크된 양측 AcceptedProposition의 전체 segment다. 이 분류는 해당 두 proposition에만 적용된다. `OVERLAPPING`은 겹치는 측면이 있는 것으로, `DISTINCT`는 서로 구별되는 것으로, `NOT_COMPARABLE`은 직접 비교할 기술적 차원이 충분히 맞지 않는 것으로 기록된 연구자 검토를 뜻한다.

#### 원문 확인

다음 provenance 항목에서 전체 segment, span 및 원문 파일을 확인할 수 있다: [P03](#p03).

### 3.2 UL Fast-ARQ trigger signaling: UL scheduling DCI와 dedicated DCI

#### 기술 질문

HARQ process failure에 대한 indication을 어떤 DCI로 전달하며, 한 개 또는 여러 process의 정보를 어떻게 나타내는가?

#### 회사별 Contribution

| 회사/조직 | TDoc | Evidence Kind | 한글 요약 | 핵심 원문 | EvidenceRef |
| --- | --- | --- | --- | --- | --- |
| vivo | R1-2603619 / RAN1 #125 | PROPOSAL / CONTRIBUTION | vivo의 R1-2603619에서는 특정 HARQ process failure에 대한 명시적 NACK indication으로 더 빠른 UL ARQ를 촉발하는 연구에서, 그 NACK indication을 UL scheduling DCI로 전달하는 방식을 제안한다. [P01](#p01) | “the explicit NACK indication is conveyed by a UL scheduling DCI.” | RAN1 / 125 / R1-2603619 / `R1-2603619 Discussion on fast ARQ.docx` / `b000023` |
| OPPO | R1-2604096 / RAN1 #125 | CONCLUSION / CONTRIBUTION | OPPO의 R1-2604096 결론 부분은 UL scheduling DCI에 명시적 ACK/NACK indication 필드를 포함하는 방식을 Option 1로 제시한다. 상위 문장은 이를 고려 가능한 선택지 중 하나로 둔다. [P07](#p07) | “An explicit ACK/NACK indication field is included in the DCI for uplink scheduling.” | RAN1 / 125 / R1-2604096 / `R1-2604096 OPPO Discussion on fast ARQ LS.docx` / `b000067` |
| OPPO | R1-2604096 / RAN1 #125 | CONCLUSION / CONTRIBUTION | OPPO의 R1-2604096 결론 부분은 여러 PUSCH/HARQ process에 대응하는 HARQ-ACK 정보를 명시적으로 알리는 dedicated DCI를 Option 2로 제시한다. 상위 문장은 이를 고려 가능한 선택지 중 하나로 둔다. [P06](#p06) | “A dedicated DCI is used to explicitly indicate HARQ-ACK information that correspond to multiple PUSCHs/HARQ processes.” | RAN1 / 125 / R1-2604096 / `R1-2604096 OPPO Discussion on fast ARQ LS.docx` / `b000068` |
| Huawei, HiSilicon | R1-2604921 / RAN1 #125 | CONCLUSION / CONTRIBUTION | Huawei·HiSilicon 공동 contribution인 R1-2604921의 결론은 특정 HARQ process 또는 process들의 failure에 대해 DCI의 명시적 indication을 사용하여 더 빠른 UL ARQ 절차를 촉발하는 방향을 제시한다. [P09](#p09) | “Support explicit indication in DCI for given HARQ process(es) failure to trigger faster UL ARQ procedure.” | RAN1 / 125 / R1-2604921 / `R1-2604921.docx` / `b000042` |

OPPO 두 option의 상위 문맥은 다음과 같다. 이 문장은 option을 고려 가능한 선택지로 한정한다. 각 option 자체의 accepted segment나 relation basis에 상위 문장을 합치지 않았다.

> Proposal 1: For triggering faster ARQ procedure in the UL, an explicit ACK/NACK indication in DCI should be supported, and the following options can be considered:

Context SourceUnit: `proposition-source-a74e2e4cacfa4a8086f92d8ef6aad9dd2ecb2460ac278a10778cef4ac07c821f`; EvidenceRef: `R1-2604096 OPPO Discussion on fast ARQ LS.docx/b000066`.

#### 검토된 Proposition Relation

아래는 기존 연구자 검토 결과다. 양측 표식은 전체 원문과 실제 proposition ID로 연결된다. 항목을 가로지르는 pair도 원래의 양측 단위를 그대로 표시했다.

| 양측 정확한 proposition | 기존 reviewed relation | Pair / Review / Accepted relation |
| --- | --- | --- |
| [P06](#p06) ↔ [P01](#p01) | DISTINCT | `proposition-pair-5596d97bf0a97f164f27073115327106b5ae76b902fca7ba96e90851a95e29fc`<br>`proposition-relation-review-5a5313fb011618d71812346fb13af7fab3a1ad404906c3e3d6389ebf0a9fe7f6`<br>`accepted-proposition-relation-2e79e069615e5e70ba348f71ebefd802efe9cb0f3d4a16cbaa2c4280f56ecb3f` |
| [P07](#p07) ↔ [P01](#p01) | OVERLAPPING | `proposition-pair-8de83c8378465b856333ca1138332f8841be3380c98e5cc13ce77ba507937acc`<br>`proposition-relation-review-cfc22b5a201afaedc0f2dae2d25768ada702fed03943bbef716fe61faefd4a99`<br>`accepted-proposition-relation-243a675da7ba2830a8b833377164ae94c8fb3a2df279662307a625d29df549b6` |
| [P09](#p09) ↔ [P01](#p01) | OVERLAPPING | `proposition-pair-8fc348379e9b2f9499087aceda2c3dd9f19a2c38e1ef07c81a9611a6928703e6`<br>`proposition-relation-review-d0940178f6f1b8ffb2aa3ca2169cf1e1a5d94bd2443a00a148cb2b1314816520`<br>`accepted-proposition-relation-0b1f70931deda4cd1288e647503b91ccd4b0a4dbcd16d2a3d980c279a8c05264` |

모든 행의 authority는 `RESEARCHER_ANALYSIS`이며, basis는 링크된 양측 AcceptedProposition의 전체 segment다. 이 분류는 해당 두 proposition에만 적용된다. `OVERLAPPING`은 겹치는 측면이 있는 것으로, `DISTINCT`는 서로 구별되는 것으로, `NOT_COMPARABLE`은 직접 비교할 기술적 차원이 충분히 맞지 않는 것으로 기록된 연구자 검토를 뜻한다.

[P09](#p09) ↔ [P07](#p07), [P09](#p09) ↔ [P06](#p06): 해당 proposition pair의 relation은 아직 review되지 않았다.

#### 원문 확인

다음 provenance 항목에서 전체 segment, span 및 원문 파일을 확인할 수 있다: [P01](#p01), [P07](#p07), [P06](#p06), [P09](#p09).

### 3.3 HARQ-ACK 신뢰도 기준선과 NACK-to-ACK 오류율 설계

#### 기술 질문

HARQ-ACK 보고 설계에서 어떤 신뢰도 기준선을 재사용하고, NACK-to-ACK 오류율에 어떤 수준을 제안하는가?

#### 회사별 Contribution

| 회사/조직 | TDoc | Evidence Kind | 한글 요약 | 핵심 원문 | EvidenceRef |
| --- | --- | --- | --- | --- | --- |
| vivo | R1-2603619 / RAN1 #125 | PROPOSAL / CONTRIBUTION | vivo의 R1-2603619에서는 HARQ-ACK feedback이 주로 HARQ 동작을 위해 설계된다고 서술한다. 6GR HARQ-ACK 보고 방식 설계 시 5G NR의 HARQ-ACK 신뢰도 요구사항을 기준선으로 재사용할 수 있다고 제안한다. [P02](#p02) | “HARQ-ACK reliability requirements for 5G NR can be reused as the baseline” | RAN1 / 125 / R1-2603619 / `R1-2603619 Discussion on fast ARQ.docx` / `b000036` |
| OPPO | R1-2604096 / RAN1 #125 | PROPOSAL / CONTRIBUTION | OPPO의 R1-2604096에서는 NACK-to-ACK 오류가 ACK-to-NACK 오류보다, 특히 지연에 민감한 트래픽에서 더 심각한 영향을 줄 수 있다고 서술한다. 이에 6RG(원문 표기)의 HARQ-ACK feedback 및 PUCCH 형식 설계에서 NACK-to-ACK 오류율을 매우 낮은 수준인 0.1%로 유지하자고 제안한다. 수치는 해당 contribution의 설계 제안이다. [P05](#p05) | “the NACK-to-ACK error rate should still be kept at a very low level, i.e., 0.1%.” | RAN1 / 125 / R1-2604096 / `R1-2604096 OPPO Discussion on fast ARQ LS.docx` / `b000054` |

#### 검토된 Proposition Relation

아래는 기존 연구자 검토 결과다. 양측 표식은 전체 원문과 실제 proposition ID로 연결된다. 항목을 가로지르는 pair도 원래의 양측 단위를 그대로 표시했다.

| 양측 정확한 proposition | 기존 reviewed relation | Pair / Review / Accepted relation |
| --- | --- | --- |
| [P05](#p05) ↔ [P08](#p08) | NOT_COMPARABLE | `proposition-pair-3d1e76bd9e1ce941894013074429f4040065c0e75b2890544f909f11bc6c11f7`<br>`proposition-relation-review-dd3f786573d834d684177e2fc7e32e4ae0362ec08c71b2626fda7f6a0fbc465f`<br>`accepted-proposition-relation-635fcaa8147972cc869cb99006ba36a895298fdb1dd412fbf18849c10e8921e6` |
| [P05](#p05) ↔ [P01](#p01) | NOT_COMPARABLE | `proposition-pair-49682b197dccbbb44f7c0b49e1cec6a4750fa3d8173ff88039dba55e35ee890a`<br>`proposition-relation-review-277b1595a6af10e32916658b865512b78c2b3458125a4200ba36802b4f3c4823`<br>`accepted-proposition-relation-9ccde0d2f3463eda8d3f15c09bfc1e3a4fc510bf200f920e129e0865ef8c5de6` |
| [P05](#p05) ↔ [P03](#p03) | NOT_COMPARABLE | `proposition-pair-c21b0489cc375858a9452f50be78602c78568f62a9b2f498a80e3f7c144a7877`<br>`proposition-relation-review-5e6dae232bd37dbd774dea438e866ea6d79666172c34fa14bda310de79477fc3`<br>`accepted-proposition-relation-746971d9e480a9375010f4e58523c4654861ab63da10776cc27afec0de13c707` |

모든 행의 authority는 `RESEARCHER_ANALYSIS`이며, basis는 링크된 양측 AcceptedProposition의 전체 segment다. 이 분류는 해당 두 proposition에만 적용된다. `OVERLAPPING`은 겹치는 측면이 있는 것으로, `DISTINCT`는 서로 구별되는 것으로, `NOT_COMPARABLE`은 직접 비교할 기술적 차원이 충분히 맞지 않는 것으로 기록된 연구자 검토를 뜻한다.

[P02](#p02) ↔ [P05](#p05): 해당 proposition pair의 relation은 아직 review되지 않았다. 공통 제목 아래 놓았다는 사실이 새 relation을 뜻하지 않는다.

#### 원문 확인

다음 provenance 항목에서 전체 segment, span 및 원문 파일을 확인할 수 있다: [P02](#p02), [P05](#p05).

### 3.4 N2A 오류 검출 및 보고

#### 기술 질문

6GR에서 N2A 오류를 L1/L2 계층에서 검출하고 보고하는 방식을 연구할 것인가?

#### 회사별 Contribution

| 회사/조직 | TDoc | Evidence Kind | 한글 요약 | 핵심 원문 | EvidenceRef |
| --- | --- | --- | --- | --- | --- |
| CATT | R1-2603887 / RAN1 #125 | PROPOSAL / CONTRIBUTION | CATT의 R1-2603887에서는 6GR에서 L1/L2 계층의 N2A 오류 검출과 해당 오류 보고 방식을 연구하자고 제안한다. 검출·보고 방식이 이미 결정됐다는 의미는 아니다. [P04](#p04) | “Study the N2A error detection at L1/L2 layer, and the corresponding error reporting mechanism in 6GR.” | RAN1 / 125 / R1-2603887 / `R1-2603887.docx` / `b000044` |

#### 검토된 Proposition Relation

아래는 기존 연구자 검토 결과다. 양측 표식은 전체 원문과 실제 proposition ID로 연결된다. 항목을 가로지르는 pair도 원래의 양측 단위를 그대로 표시했다.

| 양측 정확한 proposition | 기존 reviewed relation | Pair / Review / Accepted relation |
| --- | --- | --- |
| [P04](#p04) ↔ [P07](#p07) | NOT_COMPARABLE | `proposition-pair-0ead497923daa619e51ec11f1bd156ffc4fd831aeb87e9c309a5be1a86c29e31`<br>`proposition-relation-review-38606ebc69a2be41317d7a93ddb97c123dfe45eed7fc013b177823af5081247b`<br>`accepted-proposition-relation-a9a625f4b233533facc6bc46d968a1a22e31e3381f5d42dcaa14080194287399` |
| [P04](#p04) ↔ [P08](#p08) | NOT_COMPARABLE | `proposition-pair-75e49d303e1677561ed6df48068d7a3ef1ef7aab0ecf7dcbd7f3c95a01fef6be`<br>`proposition-relation-review-fe9e816ac2df670db3d1928a3e90fc55bc2e7d9c538e47f50318edd0f39a00bd`<br>`accepted-proposition-relation-bfb262364ecf164b27c63ec751fcf510df342255a0826c0c8e5616e701a47a01` |
| [P09](#p09) ↔ [P04](#p04) | NOT_COMPARABLE | `proposition-pair-9a9564b412beb24c04a2cc3dc6239cb1cf9e7f6b0c50d7b68e457731b913158a`<br>`proposition-relation-review-0f5aca391dd0d88315e2576c174da3364cc419121200e532b525cd9914d8bf57`<br>`accepted-proposition-relation-b6c51928bc18e534f157ec135bfc5c40f3ac46fd0da29a5cdfa30e270f7c0d5c` |

모든 행의 authority는 `RESEARCHER_ANALYSIS`이며, basis는 링크된 양측 AcceptedProposition의 전체 segment다. 이 분류는 해당 두 proposition에만 적용된다. `OVERLAPPING`은 겹치는 측면이 있는 것으로, `DISTINCT`는 서로 구별되는 것으로, `NOT_COMPARABLE`은 직접 비교할 기술적 차원이 충분히 맞지 않는 것으로 기록된 연구자 검토를 뜻한다.

#### 원문 확인

다음 provenance 항목에서 전체 segment, span 및 원문 파일을 확인할 수 있다: [P04](#p04).

### 3.5 HARQ process failure 발생 빈도

#### 기술 질문

통상적인 조건에서 HARQ process failure의 발생 빈도를 해당 contribution들은 어떻게 서술하는가?

#### 회사별 Contribution

| 회사/조직 | TDoc | Evidence Kind | 한글 요약 | 핵심 원문 | EvidenceRef |
| --- | --- | --- | --- | --- | --- |
| Samsung | R1-2604142 / RAN1 #125 | OBSERVATION / CONTRIBUTION | Samsung의 R1-2604142에서는 통상적인 조건에서 HARQ process failure가 드물게 발생한다는 관찰을 제시한다. 여기서 인용한 문장은 발생 확률의 수치를 제시하지 않는다. [P08](#p08) | “HARQ process failure is a rare event under typical conditions.” | RAN1 / 125 / R1-2604142 / `R1-2604142 Reply LS on Fast ARQ.DOCX` / `b000020` |
| Samsung | R1-2605792 / RAN1 #126 | OBSERVATION / CONTRIBUTION | Samsung의 R1-2605792에서도 통상적인 조건에서 HARQ process failure가 드물게 발생한다는 관찰을 제시한다. 별도 TDoc의 관찰로 보존하며 앞선 TDoc과의 시간적 지속성이나 진화 관계를 부여하지 않는다. [P10](#p10) | “HARQ process failure is a rare event under typical conditions.” | RAN1 / 126 / R1-2605792 / `R1-2605792 Reply LS on Fast ARQ Final.docx` / `b000020` |

#### 검토된 Proposition Relation

아래는 기존 연구자 검토 결과다. 양측 표식은 전체 원문과 실제 proposition ID로 연결된다. 항목을 가로지르는 pair도 원래의 양측 단위를 그대로 표시했다.

| 양측 정확한 proposition | 기존 reviewed relation | Pair / Review / Accepted relation |
| --- | --- | --- |
| [P09](#p09) ↔ [P10](#p10) | NOT_COMPARABLE | `proposition-pair-833a016498bfde173efff0131ac211257587bfce47cdab7f98c08269c481133d`<br>`proposition-relation-review-87d03dff0a33b544066e0bf4c5af7af73b7a9ef6e61d3f8a625909454babb8e5`<br>`accepted-proposition-relation-48a094a5e413cd9147c9a23becdebad3c06b1f7743aa9e0c4a5060951421da15` |

모든 행의 authority는 `RESEARCHER_ANALYSIS`이며, basis는 링크된 양측 AcceptedProposition의 전체 segment다. 이 분류는 해당 두 proposition에만 적용된다. `OVERLAPPING`은 겹치는 측면이 있는 것으로, `DISTINCT`는 서로 구별되는 것으로, `NOT_COMPARABLE`은 직접 비교할 기술적 차원이 충분히 맞지 않는 것으로 기록된 연구자 검토를 뜻한다.

[P08](#p08)와 [P10](#p10)은 서로 다른 회의의 별도 원문이다. 두 문장은 동일한 조직 메타데이터를 가지므로 기본 cross-organization pair 범위에서 제외된다. 본 보고서는 두 문장 사이에 reviewed relation이나 시간적 진화 관계를 부여하지 않는다.

#### 원문 확인

다음 provenance 항목에서 전체 segment, span 및 원문 파일을 확인할 수 있다: [P08](#p08), [P10](#p10).

## 4. 회사별 빠른 인덱스

| 조직 메타데이터 | 보고서 technical item | TDoc / proposition |
| --- | --- | --- |
| CATT | 3.1, 3.4 | R1-2603887 [P03](#p03); R1-2603887 [P04](#p04) |
| HiSilicon | 3.2 | R1-2604921 [P09](#p09) |
| Huawei | 3.2 | R1-2604921 [P09](#p09) |
| OPPO | 3.2, 3.3 | R1-2604096 [P05](#p05); R1-2604096 [P06](#p06); R1-2604096 [P07](#p07) |
| Samsung | 3.5 | R1-2604142 [P08](#p08); R1-2605792 [P10](#p10) |
| vivo | 3.2, 3.3 | R1-2603619 [P01](#p01); R1-2603619 [P02](#p02) |

Huawei와 HiSilicon은 R1-2604921의 공동 조직 메타데이터다. 두 이름을 별도로 색인하지만, [P09](#p09) 또는 그 관계를 두 개의 독립 주장으로 중복 계산하지 않는다.

## 5. 원문 파일 인덱스

### 5.1 로컬 원문과 normalized artifact

아래 파일 경로는 실제 존재와 checksum을 확인했다. Member는 실제 raw ZIP 내부 이름이며, 독립 로컬 파일 경로로 표기하지 않는다. 링크는 이 보고서 파일 위치를 기준으로 저장소 안의 파일을 가리킨다.

| TDoc | 조직 | Meeting | Raw artifact | Member | Normalized artifact | 주요 EvidenceRef |
| --- | --- | --- | --- | --- | --- | --- |
| R1-2603619 | vivo | RAN1 #125 | [data/raw/tdocs/ran1/125/R1-2603619/R1-2603619.zip](<../data/raw/tdocs/ran1/125/R1-2603619/R1-2603619.zip>) | `R1-2603619 Discussion on fast ARQ.docx` (ZIP member) | [data/normalized/documents/ran1/125/R1-2603619/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2603619/document.jsonl.gz>) | [P01](#p01) `b000023`<br>[P02](#p02) `b000036` |
| R1-2603887 | CATT | RAN1 #125 | [data/raw/tdocs/ran1/125/R1-2603887/R1-2603887.zip](<../data/raw/tdocs/ran1/125/R1-2603887/R1-2603887.zip>) | `R1-2603887.docx` (ZIP member) | [data/normalized/documents/ran1/125/R1-2603887/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2603887/document.jsonl.gz>) | [P03](#p03) `b000029`<br>[P04](#p04) `b000044` |
| R1-2604096 | OPPO | RAN1 #125 | [data/raw/tdocs/ran1/125/R1-2604096/R1-2604096.zip](<../data/raw/tdocs/ran1/125/R1-2604096/R1-2604096.zip>) | `R1-2604096 OPPO Discussion on fast ARQ LS.docx` (ZIP member) | [data/normalized/documents/ran1/125/R1-2604096/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2604096/document.jsonl.gz>) | [P05](#p05) `b000054`<br>[P06](#p06) `b000068`<br>[P07](#p07) `b000067` |
| R1-2604142 | Samsung | RAN1 #125 | [data/raw/tdocs/ran1/125/R1-2604142/R1-2604142.zip](<../data/raw/tdocs/ran1/125/R1-2604142/R1-2604142.zip>) | `R1-2604142 Reply LS on Fast ARQ.DOCX` (ZIP member) | [data/normalized/documents/ran1/125/R1-2604142/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2604142/document.jsonl.gz>) | [P08](#p08) `b000020` |
| R1-2604921 | Huawei, HiSilicon | RAN1 #125 | [data/raw/tdocs/ran1/125/R1-2604921/R1-2604921.zip](<../data/raw/tdocs/ran1/125/R1-2604921/R1-2604921.zip>) | `R1-2604921.docx` (ZIP member) | [data/normalized/documents/ran1/125/R1-2604921/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2604921/document.jsonl.gz>) | [P09](#p09) `b000042` |
| R1-2605792 | Samsung | RAN1 #126 | [data/raw/tdocs/ran1/126/R1-2605792/R1-2605792.zip](<../data/raw/tdocs/ran1/126/R1-2605792/R1-2605792.zip>) | `R1-2605792 Reply LS on Fast ARQ Final.docx` (ZIP member) | [data/normalized/documents/ran1/126/R1-2605792/document.jsonl.gz](<../data/normalized/documents/ran1/126/R1-2605792/document.jsonl.gz>) | [P10](#p10) `b000020` |

공식 URL은 이미 저장된 metadata/receipt에서 읽었다. URL에 접속하거나 자료를 추가 취득하지 않았다.

| TDoc | 저장된 metadata official URL | Raw receipt URL | Raw SHA-256 / Normalized checksum |
| --- | --- | --- | --- |
| R1-2603619 | https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603619.zip | https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603619.zip | `f691708f821275a0aac66596a27bdd8e4a89ecb75094fce2605a0abc0b37b2f9`<br>`7659c2421f9a74eb5fec74f3045d89069a4a27797aae1fdfa001b53be7ef2f8b` |
| R1-2603887 | https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603887.zip | https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603887.zip | `c696ba693dda40b0414511c41dca748077b8cfa8e21b55f9f328338e96aad7cb`<br>`931fc31d4bf9aaf1833dd659d7ee7d822f0fd888b5600ef9f7b3f82c2b80e436` |
| R1-2604096 | https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604096.zip | https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604096.zip | `f230c16571379979a1e9004b9d874b049a2e745a36cd4654bd09122326df6cc6`<br>`fd780b0964d8832be0e445bb4bc4a121ac412146d86389e109b1dddd0bf0c5a8` |
| R1-2604142 | https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604142.zip | https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604142.zip | `c9cc66958206b7f60fc73d4bb3ca29138394af798b96d6c6fc69558c82b045ed`<br>`749daf11cf96c93de74aff55a0030e7c6b981282d274bab78b7a26e130679055` |
| R1-2604921 | https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604921.zip | https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604921.zip | `a8742c8e0d4e7d6f07647bc118eb365739555dd3bb22b8841d5c45f7a4deee88`<br>`226803ade9f1fbc5350e347bcf9977b08aaef079c89b56591b9859c3a5ad6688` |
| R1-2605792 | https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Docs/R1-2605792.zip | https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Docs/R1-2605792.zip | `276ff552cc714aed9cbd8bb058e83d303f5d8ea6d27ed833498ca9debd37599f`<br>`c540607a3434e81ddcf0889c2f0576e2185e7dbbde4de55d8328b50238a457ed` |

### 5.2 Proposition별 전체 원문과 출처

아래 전체 원문은 AcceptedProposition segment의 정확한 복사다. §3 relation 표의 bilateral basis 역시 이 전체 segment다. 한국어 요약은 보고서의 설명문이며 원문 증거·proposition·relation으로 저장하지 않는다.

<a id="p01"></a>

#### P01 — R1-2603619 / PROPOSAL

- 조직 메타데이터: vivo
- Meeting: RAN1 #125; Scope: `CONTRIBUTION`
- EvidenceRef: RAN1 / 125 / R1-2603619 / `R1-2603619 Discussion on fast ARQ.docx` / `b000023`
- AcceptedProposition ID: `accepted-proposition-d2940d4700b1093aae1d0043f64bb6840f41b123284f6f74db2ffe85458d13ed`
- Proposition review ID: `proposition-review-4e299446f4902cbcc61711b512b58ea02dccebc0bb67736106e9cf14aa38a644`
- SemanticEvidence ID: `ev-380dbae3a6b0d247774d27f0`
- SourceUnit ID: `proposition-source-76eba7d9b725f77dac947885fad5f259de816a831d9b6cafea431775c79ea005`
- Candidate ID: `proposition-candidate-42e889a6069a804821b36546383dfe46d5318f1edc17d8b923e7aa6835455813`
- Raw contribution: [data/raw/tdocs/ran1/125/R1-2603619/R1-2603619.zip](<../data/raw/tdocs/ran1/125/R1-2603619/R1-2603619.zip>)
- Normalized document: [data/normalized/documents/ran1/125/R1-2603619/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2603619/document.jsonl.gz>)
- 저장된 official URL: https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603619.zip
- SourceUnit 내 accepted span (0-based, end exclusive): [0, 193)
- Normalized EvidenceRef span (0-based, end exclusive): `b000023` [0, 193)

> Proposal 1: For the study of an explicit NACK indication for a given HARQ process failure to trigger faster ARQ procedure in UL, the explicit NACK indication is conveyed by a UL scheduling DCI.

<a id="p02"></a>

#### P02 — R1-2603619 / PROPOSAL

- 조직 메타데이터: vivo
- Meeting: RAN1 #125; Scope: `CONTRIBUTION`
- EvidenceRef: RAN1 / 125 / R1-2603619 / `R1-2603619 Discussion on fast ARQ.docx` / `b000036`
- AcceptedProposition ID: `accepted-proposition-882f41a4ea1a1e21e0e3a4b93490bc14a8436b9f27dd2d11b13db953851d7b6a`
- Proposition review ID: `proposition-review-87e78a3b03910e399cb9df213fc6727621183136c79c38eaff326baeb2676f6d`
- SemanticEvidence ID: `ev-b4c7b241be085eb04e80859e`
- SourceUnit ID: `proposition-source-d18f4c3005096b79c27da2f5e4db885515df7989fd62c8f02a28f8a3b1f1dc67`
- Candidate ID: `proposition-candidate-8a319da7621250e3888487417be75411d66ba80764e1a08c0b96cb739ab3aa5d`
- Raw contribution: [data/raw/tdocs/ran1/125/R1-2603619/R1-2603619.zip](<../data/raw/tdocs/ran1/125/R1-2603619/R1-2603619.zip>)
- Normalized document: [data/normalized/documents/ran1/125/R1-2603619/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2603619/document.jsonl.gz>)
- 저장된 official URL: https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603619.zip
- SourceUnit 내 accepted span (0-based, end exclusive): [0, 202)
- Normalized EvidenceRef span (0-based, end exclusive): `b000036` [0, 358)

> Proposal 3: HARQ-ACK feedback is designed primarily for HARQ operation, where HARQ-ACK reliability requirements for 5G NR can be reused as the baseline in design of HARQ-ACK reporting mechanism for 6GR.

<a id="p03"></a>

#### P03 — R1-2603887 / OBSERVATION

- 조직 메타데이터: CATT
- Meeting: RAN1 #125; Scope: `CONTRIBUTION`
- EvidenceRef: RAN1 / 125 / R1-2603887 / `R1-2603887.docx` / `b000029`
- AcceptedProposition ID: `accepted-proposition-7fb683de78237928efe6803a19a1fcd34336a93fc6f16a775e6e2974ad5c5655`
- Proposition review ID: `proposition-review-4a11cf7dc25ebd141857bd387a1d04213c3253dde1a383aa5d185afd11b98e47`
- SemanticEvidence ID: `ev-63483145dc53f8821271fade`
- SourceUnit ID: `proposition-source-156002a1169d79e99fe258b3c20493d44444d774e36e36316e91071a1b95b72a`
- Candidate ID: `proposition-candidate-2f9dc6d3b10049f0b227888a36b7c19e18f62eafed25226bb4e88921d201eda4`
- Raw contribution: [data/raw/tdocs/ran1/125/R1-2603887/R1-2603887.zip](<../data/raw/tdocs/ran1/125/R1-2603887/R1-2603887.zip>)
- Normalized document: [data/normalized/documents/ran1/125/R1-2603887/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2603887/document.jsonl.gz>)
- 저장된 official URL: https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603887.zip
- SourceUnit 내 accepted span (0-based, end exclusive): [0, 182)
- Normalized EvidenceRef span (0-based, end exclusive): `b000029` [0, 182)

> Observation 1： Regarding HARQ process status indication, it can be left to the signaling design to choose either only indicating HARQ NACK or supporting explicit ACK/NACK indication.

<a id="p04"></a>

#### P04 — R1-2603887 / PROPOSAL

- 조직 메타데이터: CATT
- Meeting: RAN1 #125; Scope: `CONTRIBUTION`
- EvidenceRef: RAN1 / 125 / R1-2603887 / `R1-2603887.docx` / `b000044`
- AcceptedProposition ID: `accepted-proposition-6b241d8f070a8942f3590981ade2192823fa65d6dc248fed3b66c32737d34144`
- Proposition review ID: `proposition-review-5105884347626f39d2291897603337a70e7d66cbd4bf967906ba6c76b52c050e`
- SemanticEvidence ID: `ev-53f75e517a0aa022f746c18c`
- SourceUnit ID: `proposition-source-e8452f4ca13ee781440c8b61e6ca03fbf7c0d7f434b29773b0ad3f86af409a7f`
- Candidate ID: `proposition-candidate-5dcdc73ea21dd868c169deb4759344df3e2551c6dbedf4ea3cbfe90e22065e1e`
- Raw contribution: [data/raw/tdocs/ran1/125/R1-2603887/R1-2603887.zip](<../data/raw/tdocs/ran1/125/R1-2603887/R1-2603887.zip>)
- Normalized document: [data/normalized/documents/ran1/125/R1-2603887/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2603887/document.jsonl.gz>)
- 저장된 official URL: https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603887.zip
- SourceUnit 내 accepted span (0-based, end exclusive): [0, 113)
- Normalized EvidenceRef span (0-based, end exclusive): `b000044` [0, 113)

> Proposal 4: Study the N2A error detection at L1/L2 layer, and the corresponding error reporting mechanism in 6GR.

<a id="p05"></a>

#### P05 — R1-2604096 / PROPOSAL

- 조직 메타데이터: OPPO
- Meeting: RAN1 #125; Scope: `CONTRIBUTION`
- EvidenceRef: RAN1 / 125 / R1-2604096 / `R1-2604096 OPPO Discussion on fast ARQ LS.docx` / `b000054`
- AcceptedProposition ID: `accepted-proposition-569dc7a220f3baaa17774de0bd803d0f7295a921a2d0bfae0d182b3009f119a7`
- Proposition review ID: `proposition-review-4d401852658ec061431f29d4b68847df12cc8c902e5f6d2ef87b40c814da8261`
- SemanticEvidence ID: `ev-b574c6e3f6afe16c0119c791`
- SourceUnit ID: `proposition-source-9e8afb229b28927e5fc5f194e6969caf7a7abce9c05c747d610fe1adf3b64a4e`
- Candidate ID: `proposition-candidate-b39be7047c7371fb1d5fd7a71b6de31f0969540d8932f756a36728c3643533d0`
- Raw contribution: [data/raw/tdocs/ran1/125/R1-2604096/R1-2604096.zip](<../data/raw/tdocs/ran1/125/R1-2604096/R1-2604096.zip>)
- Normalized document: [data/normalized/documents/ran1/125/R1-2604096/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2604096/document.jsonl.gz>)
- 저장된 official URL: https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604096.zip
- SourceUnit 내 accepted span (0-based, end exclusive): [0, 307)
- Normalized EvidenceRef span (0-based, end exclusive): `b000054` [0, 307)

> With the above, we think the NACK-to-ACK error can cause more serious impact than ACK to NACK error, especially for latency-sensitive traffic and hence we propose that in the designs of 6RG HARQ-ACK feedback and PUCCH formats, the NACK-to-ACK error rate should still be kept at a very low level, i.e., 0.1%.

<a id="p06"></a>

#### P06 — R1-2604096 / CONCLUSION

- 조직 메타데이터: OPPO
- Meeting: RAN1 #125; Scope: `CONTRIBUTION`
- EvidenceRef: RAN1 / 125 / R1-2604096 / `R1-2604096 OPPO Discussion on fast ARQ LS.docx` / `b000068`
- AcceptedProposition ID: `accepted-proposition-5797c4b6ee707f2edad3f5560ed3255545a0bab104e5355055eb29b582831d9e`
- Proposition review ID: `proposition-review-51bae3326d30303a211ff4153dcbe6ba98404d027396eede02e84f8bc3390589`
- SemanticEvidence ID: `ev-1a0c47ad432160a6d651ac24`
- SourceUnit ID: `proposition-source-21a6ca015c68dd2dee5b634b7bd81bf26e4e8dd94bbe197624841c7685f75d2d`
- Candidate ID: `proposition-candidate-bd7b74235d415ba2bdeb02abc2e4b90cf9a4d9772ea0882e0cfeebd255faeca4`
- Raw contribution: [data/raw/tdocs/ran1/125/R1-2604096/R1-2604096.zip](<../data/raw/tdocs/ran1/125/R1-2604096/R1-2604096.zip>)
- Normalized document: [data/normalized/documents/ran1/125/R1-2604096/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2604096/document.jsonl.gz>)
- 저장된 official URL: https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604096.zip
- SourceUnit 내 accepted span (0-based, end exclusive): [0, 128)
- Normalized EvidenceRef span (0-based, end exclusive): `b000068` [0, 128)
- 별도 parent context: `proposition-source-a74e2e4cacfa4a8086f92d8ef6aad9dd2ecb2460ac278a10778cef4ac07c821f` (§3.2); 관계 basis에 포함하지 않음

> Option 2: A dedicated DCI is used to explicitly indicate HARQ-ACK information that correspond to multiple PUSCHs/HARQ processes.

<a id="p07"></a>

#### P07 — R1-2604096 / CONCLUSION

- 조직 메타데이터: OPPO
- Meeting: RAN1 #125; Scope: `CONTRIBUTION`
- EvidenceRef: RAN1 / 125 / R1-2604096 / `R1-2604096 OPPO Discussion on fast ARQ LS.docx` / `b000067`
- AcceptedProposition ID: `accepted-proposition-8d05c029c2ebcfe8aaa7f12fac99fc10d7889f10aa7cbd1ff1570a223a2fcc14`
- Proposition review ID: `proposition-review-3905f18d7d334a34fa9f838fed937a487309d09a810d437a50f2eeedd545694f`
- SemanticEvidence ID: `ev-27bf76b1a9797f9f55e9b674`
- SourceUnit ID: `proposition-source-8e006be482ba3d8cff1136f95327870e1bbdd39905d36ad42130eccf68d88be2`
- Candidate ID: `proposition-candidate-e9dfd9ee275b402c6acaf1b80642d803da59313bac3e02bf7701ecb4b9998225`
- Raw contribution: [data/raw/tdocs/ran1/125/R1-2604096/R1-2604096.zip](<../data/raw/tdocs/ran1/125/R1-2604096/R1-2604096.zip>)
- Normalized document: [data/normalized/documents/ran1/125/R1-2604096/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2604096/document.jsonl.gz>)
- 저장된 official URL: https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604096.zip
- SourceUnit 내 accepted span (0-based, end exclusive): [0, 93)
- Normalized EvidenceRef span (0-based, end exclusive): `b000067` [0, 93)
- 별도 parent context: `proposition-source-a74e2e4cacfa4a8086f92d8ef6aad9dd2ecb2460ac278a10778cef4ac07c821f` (§3.2); 관계 basis에 포함하지 않음

> Option 1: An explicit ACK/NACK indication field is included in the DCI for uplink scheduling.

<a id="p08"></a>

#### P08 — R1-2604142 / OBSERVATION

- 조직 메타데이터: Samsung
- Meeting: RAN1 #125; Scope: `CONTRIBUTION`
- EvidenceRef: RAN1 / 125 / R1-2604142 / `R1-2604142 Reply LS on Fast ARQ.DOCX` / `b000020`
- AcceptedProposition ID: `accepted-proposition-851ba12b3a15286ff6461b2ab81cb889d75180234e1ae04f3553b3ee243d8717`
- Proposition review ID: `proposition-review-11e603ec004bd31c260f551014fd14f5f86a23913d5db2747f286d5541f9740f`
- SemanticEvidence ID: `ev-f75bffcaf2cd334fbd77ce72`
- SourceUnit ID: `proposition-source-856b6940832cdcc23249e49a60d91cc9a7e392252875041a038f224d8934dc28`
- Candidate ID: `proposition-candidate-658fd73385caa0e94eeeee52300f06b075c71ca3a7c348bbfe7108a99e66d587`
- Raw contribution: [data/raw/tdocs/ran1/125/R1-2604142/R1-2604142.zip](<../data/raw/tdocs/ran1/125/R1-2604142/R1-2604142.zip>)
- Normalized document: [data/normalized/documents/ran1/125/R1-2604142/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2604142/document.jsonl.gz>)
- 저장된 official URL: https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604142.zip
- SourceUnit 내 accepted span (0-based, end exclusive): [0, 77)
- Normalized EvidenceRef span (0-based, end exclusive): `b000020` [0, 77)

> Observation 1: HARQ process failure is a rare event under typical conditions.

<a id="p09"></a>

#### P09 — R1-2604921 / CONCLUSION

- 조직 메타데이터: Huawei, HiSilicon
- Meeting: RAN1 #125; Scope: `CONTRIBUTION`
- EvidenceRef: RAN1 / 125 / R1-2604921 / `R1-2604921.docx` / `b000042`
- AcceptedProposition ID: `accepted-proposition-13458cbe477a160fcb855ce8a8eac6b0ae5a939508b788ac7839ca43594d61fe`
- Proposition review ID: `proposition-review-9c7051c0703186adf843eba21bd00780984780d5460e0139c50bd9f8a22ef57e`
- SemanticEvidence ID: `ev-0f389c93124c2a7af6ceaf7d`
- SourceUnit ID: `proposition-source-a19a74c70adcacd9ccb2b6b6b9004bbdb4e63be95d577010e6f9a41a456c95b1`
- Candidate ID: `proposition-candidate-7e518c6be8bdcfcbcdaee879d3bbaad3195b076d51ce849a016e47b0c4d74ece`
- Raw contribution: [data/raw/tdocs/ran1/125/R1-2604921/R1-2604921.zip](<../data/raw/tdocs/ran1/125/R1-2604921/R1-2604921.zip>)
- Normalized document: [data/normalized/documents/ran1/125/R1-2604921/document.jsonl.gz](<../data/normalized/documents/ran1/125/R1-2604921/document.jsonl.gz>)
- 저장된 official URL: https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604921.zip
- SourceUnit 내 accepted span (0-based, end exclusive): [0, 105)
- Normalized EvidenceRef span (0-based, end exclusive): `b000042` [0, 105)

> Support explicit indication in DCI for given HARQ process(es) failure to trigger faster UL ARQ procedure.

<a id="p10"></a>

#### P10 — R1-2605792 / OBSERVATION

- 조직 메타데이터: Samsung
- Meeting: RAN1 #126; Scope: `CONTRIBUTION`
- EvidenceRef: RAN1 / 126 / R1-2605792 / `R1-2605792 Reply LS on Fast ARQ Final.docx` / `b000020`
- AcceptedProposition ID: `accepted-proposition-ef85dffc7832b8ec5739231df8e6124d4ff063ffbdb5b8436d4733056327c664`
- Proposition review ID: `proposition-review-ac3df2d43f9e90851b92ac3dc30fe34a867c4e958c41604dfa89f08da18495fe`
- SemanticEvidence ID: `ev-c2fdc7a412538d515c3bc8b2`
- SourceUnit ID: `proposition-source-6bde8181241db8a3250fbdf8d8f9c36d69299d3c4507bea2eb2cc69db6a80d1e`
- Candidate ID: `proposition-candidate-bc3f2cdfb6dd991d547fbdc76e92da334d57e69f3c52ae1933b2aebff9ceaef9`
- Raw contribution: [data/raw/tdocs/ran1/126/R1-2605792/R1-2605792.zip](<../data/raw/tdocs/ran1/126/R1-2605792/R1-2605792.zip>)
- Normalized document: [data/normalized/documents/ran1/126/R1-2605792/document.jsonl.gz](<../data/normalized/documents/ran1/126/R1-2605792/document.jsonl.gz>)
- 저장된 official URL: https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Docs/R1-2605792.zip
- SourceUnit 내 accepted span (0-based, end exclusive): [0, 77)
- Normalized EvidenceRef span (0-based, end exclusive): `b000020` [0, 77)

> Observation 1: HARQ process failure is a rare event under typical conditions.

### 5.3 검토 artifact 위치

| Artifact | 실제 로컬 파일 | SHA-256 |
| --- | --- | --- |
| TopicTerminologyProfile | [data/derived/topics/ran1/topic-profile-e0e7f5ed87ddc3618136922d8239009f69bb8847cb53f3560713185902ec302d/topic-profile.json](<../data/derived/topics/ran1/topic-profile-e0e7f5ed87ddc3618136922d8239009f69bb8847cb53f3560713185902ec302d/topic-profile.json>) | `43b50bbc4d88e011fc3a1cd24ed613e63cdd47aaa21c62ce8d39fa64723b9a5d` |
| V0.12 corpus.json | [data/derived/propositions/RAN1/topic-proposition-corpus-bb963771ac1e03deaff0345bc72bb86ae052d016f5a670c5c94c1676f79cdd43/corpus.json](<../data/derived/propositions/RAN1/topic-proposition-corpus-bb963771ac1e03deaff0345bc72bb86ae052d016f5a670c5c94c1676f79cdd43/corpus.json>) | `53929206a7eda89fd895e689fe1893b2cf95c849d22e5f597a9a85666dcc09bc` |
| V0.12 source-units.jsonl.gz | [data/derived/propositions/RAN1/topic-proposition-corpus-bb963771ac1e03deaff0345bc72bb86ae052d016f5a670c5c94c1676f79cdd43/source-units.jsonl.gz](<../data/derived/propositions/RAN1/topic-proposition-corpus-bb963771ac1e03deaff0345bc72bb86ae052d016f5a670c5c94c1676f79cdd43/source-units.jsonl.gz>) | `edfd9118688820c70b98540316d7649880dace7021539bce7a8b38d20ab13b74` |
| V0.12 candidates.jsonl.gz | [data/derived/propositions/RAN1/topic-proposition-corpus-bb963771ac1e03deaff0345bc72bb86ae052d016f5a670c5c94c1676f79cdd43/candidates.jsonl.gz](<../data/derived/propositions/RAN1/topic-proposition-corpus-bb963771ac1e03deaff0345bc72bb86ae052d016f5a670c5c94c1676f79cdd43/candidates.jsonl.gz>) | `0ddd6e28d92ef698a688a1253c581b8db6255e066148756c2a466e63222b9a74` |
| V0.12 reviews.jsonl | [data/derived/propositions/RAN1/topic-proposition-corpus-bb963771ac1e03deaff0345bc72bb86ae052d016f5a670c5c94c1676f79cdd43/reviews.jsonl](<../data/derived/propositions/RAN1/topic-proposition-corpus-bb963771ac1e03deaff0345bc72bb86ae052d016f5a670c5c94c1676f79cdd43/reviews.jsonl>) | `54bb168861a6e27449e0d548adc1a2ebdc0fc63ddbdd24b09f2b314b5991d7a1` |
| V0.12 accepted-propositions.jsonl.gz | [data/derived/propositions/RAN1/topic-proposition-corpus-bb963771ac1e03deaff0345bc72bb86ae052d016f5a670c5c94c1676f79cdd43/accepted-propositions.jsonl.gz](<../data/derived/propositions/RAN1/topic-proposition-corpus-bb963771ac1e03deaff0345bc72bb86ae052d016f5a670c5c94c1676f79cdd43/accepted-propositions.jsonl.gz>) | `59e15c395f21df31897ff59abaf0fc4bfa9144d809d3b94540357f2832b7e8d6` |
| V0.13 corpus.json | [data/derived/proposition-relations/RAN1/proposition-relation-corpus-d3ea80f8d89034f51a799f73e6af829f1654c91bb88fa4da01c8b9bdda8bc116/corpus.json](<../data/derived/proposition-relations/RAN1/proposition-relation-corpus-d3ea80f8d89034f51a799f73e6af829f1654c91bb88fa4da01c8b9bdda8bc116/corpus.json>) | `e8ef7e3cedc62b47e2d4c86b345e9b197a992c8bed76edad4d0f58bff0c29e02` |
| V0.13 pair-candidates.jsonl.gz | [data/derived/proposition-relations/RAN1/proposition-relation-corpus-d3ea80f8d89034f51a799f73e6af829f1654c91bb88fa4da01c8b9bdda8bc116/pair-candidates.jsonl.gz](<../data/derived/proposition-relations/RAN1/proposition-relation-corpus-d3ea80f8d89034f51a799f73e6af829f1654c91bb88fa4da01c8b9bdda8bc116/pair-candidates.jsonl.gz>) | `5c4e1867517cb0c929e76e252c055ca7eb0b1614299444b53098c81454928e3a` |
| V0.13 reviews.jsonl | [data/derived/proposition-relations/RAN1/proposition-relation-corpus-d3ea80f8d89034f51a799f73e6af829f1654c91bb88fa4da01c8b9bdda8bc116/reviews.jsonl](<../data/derived/proposition-relations/RAN1/proposition-relation-corpus-d3ea80f8d89034f51a799f73e6af829f1654c91bb88fa4da01c8b9bdda8bc116/reviews.jsonl>) | `5be4e905b18b499c8e877d22a45b968ebec4066e1245556d5840b6cafacfc6d7` |
| V0.13 accepted-relations.jsonl.gz | [data/derived/proposition-relations/RAN1/proposition-relation-corpus-d3ea80f8d89034f51a799f73e6af829f1654c91bb88fa4da01c8b9bdda8bc116/accepted-relations.jsonl.gz](<../data/derived/proposition-relations/RAN1/proposition-relation-corpus-d3ea80f8d89034f51a799f73e6af829f1654c91bb88fa4da01c8b9bdda8bc116/accepted-relations.jsonl.gz>) | `48353d174e86a540eb0375e4c822c842e440cd263382833376552b2c0d5bf1a9` |

direct inventory는 기존 API로 메모리에서 재계산하여 V0.12 manifest의 inventory ID와 일치함을 확인했다. 새 inventory artifact는 저장하지 않았다.

## 6. 해석 시 주의사항

- `OVERLAPPING`은 검토된 두 proposition 사이의 주석이다. 회사 간 합의나 같은 공식 입장으로 확대하지 않는다.
- `DISTINCT`는 Pair에 기록된 기존 분류다. 회사 간 반대·충돌로 바꾸지 않는다.
- `NOT_COMPARABLE`은 해당 검토 단위에 대한 연구자 분류다. 기업 간 무관함·거절·반대나 증거 누락을 뜻하지 않는다.
- OBSERVATION과 CONCLUSION은 원래 종류를 유지한다. 특히 contribution conclusion을 meeting conclusion으로 승격하지 않는다.
- `under typical conditions`, `can be reused`, `for the study`, `Study`, OPPO의 고려 가능한 option 문맥을 유지한다. OPPO 원문의 `6RG` 표기는 그대로 인용하며, 보고서가 임의로 원문을 수정하지 않는다.
- 동일 문구·같은 기술 항목·다른 회의에서의 재등장만으로 새 relation, 조직 입장, consensus, adoption 또는 시간적 진화를 만들지 않는다.
- Chair Note의 미등장은 미논의의 증거가 아니며, 현재 선택된 자료의 완전성을 가정하지 않는다. 검토되지 않은 proposition은 negative evidence가 아니다.

### 6.1 아직 review되지 않은 비교

전체 eligible cross-organization pair 39개 중 기존 검토 12개를 모두 인용했다. 아래 27개는 저장된 pair 집합에서 review가 없는 항목 전부다. 아래 각 행에 대해 **해당 proposition pair의 relation은 아직 review되지 않았다.** 이 목록은 새로운 기술적 분류를 제시하지 않는다. 동일 조직 메타데이터가 겹쳐 생성되지 않은 pair는 이 숫자에 포함하지 않는다.

| 양측 proposition | 실제 pair ID | 상태 |
| --- | --- | --- |
| [P01](#p01) ↔ [P10](#p10) | `proposition-pair-586c8a0e3ef683fd57aed353d0f0c08fca03682b31d52998a94abeca45f69d08` | UNREVIEWED |
| [P02](#p02) ↔ [P07](#p07) | `proposition-pair-f832225a55a5ed471b4d32bdf1a97b8af03e8a957c09c49e7ec5f660cbdff037` | UNREVIEWED |
| [P02](#p02) ↔ [P10](#p10) | `proposition-pair-87ddfda7f193f81d287f53ebc6e7684ead3fdc655390007afdd841bd6de892c2` | UNREVIEWED |
| [P03](#p03) ↔ [P02](#p02) | `proposition-pair-755330ac3ac018aec5c054dc70befc968ece8a79331f1eb3dc44082de73b26b5` | UNREVIEWED |
| [P03](#p03) ↔ [P08](#p08) | `proposition-pair-48c17169357f18d22180ae74f290b8095cadfa1df5af06248bcbff5e6b19e83b` | UNREVIEWED |
| [P03](#p03) ↔ [P10](#p10) | `proposition-pair-caee70c47229f7d2f126d0173261e2855414a50abd105446274281f72e923eeb` | UNREVIEWED |
| [P04](#p04) ↔ [P01](#p01) | `proposition-pair-f538eeb7d97199d1a20dae3f438cbc8eab2e9ab6ba04f75a2ee8b39eab8d38cb` | UNREVIEWED |
| [P04](#p04) ↔ [P02](#p02) | `proposition-pair-25e760acc05c12b0b67455bcc1141fe7e4208957e51c7e9c3930c6be4de2172c` | UNREVIEWED |
| [P04](#p04) ↔ [P10](#p10) | `proposition-pair-65ade6a84a0d869ee30e5c96a8b50af27a074ab417e0af498c37d57e3a012acf` | UNREVIEWED |
| [P05](#p05) ↔ [P02](#p02) | `proposition-pair-9b6c1c04b15db0b37fc85e667e378ae595f5dab54a1197f2660729c82a5a4b3d` | UNREVIEWED |
| [P05](#p05) ↔ [P04](#p04) | `proposition-pair-1a2be7c4f924e3d9ab1d1b001e6bb864ab79baa59323b089380c071659ac3527` | UNREVIEWED |
| [P05](#p05) ↔ [P10](#p10) | `proposition-pair-f6eddcd31bbc4e4a14001373632f51558e0f4dc335856a7e329d1511210e07d5` | UNREVIEWED |
| [P06](#p06) ↔ [P02](#p02) | `proposition-pair-860bf9ac44c7b6bcb71f5b93629bc4c30fc7e3ba80c1119ee6667d2b21aaba99` | UNREVIEWED |
| [P06](#p06) ↔ [P03](#p03) | `proposition-pair-32d0b3a3ed96a7c42e6922f0b950612f672e0a4b5b874bae911230454cba6011` | UNREVIEWED |
| [P06](#p06) ↔ [P04](#p04) | `proposition-pair-2e93fc08513508c2916937c39036e6237dc45841e1cc43b43828fb91228a25c7` | UNREVIEWED |
| [P06](#p06) ↔ [P08](#p08) | `proposition-pair-c357e8928212802e047dead145b3a4e6f4a40e4ba7c346db131e87112b2cae3a` | UNREVIEWED |
| [P06](#p06) ↔ [P10](#p10) | `proposition-pair-1d276cb33bb5ef9655cf8af37475c16b3590e119f9c04de3f0aeed7e46f80775` | UNREVIEWED |
| [P07](#p07) ↔ [P10](#p10) | `proposition-pair-d82cbd8800fdae9b3598a87be2576c0703f48be692212b47ca00b633c94f88d9` | UNREVIEWED |
| [P08](#p08) ↔ [P01](#p01) | `proposition-pair-9ef1602e3f608ad63d39ad8960187fb20f2ca5f9e6fd54f32ac97e225fc52986` | UNREVIEWED |
| [P08](#p08) ↔ [P02](#p02) | `proposition-pair-b15b474f058f2a082de51f56789f0058925c5413bfb6a8286cae488ebd42fafd` | UNREVIEWED |
| [P08](#p08) ↔ [P07](#p07) | `proposition-pair-52e82a8680d5d8bbc213ad82d28eeab5d16fbea57a76aaf57a9f4e782a2db757` | UNREVIEWED |
| [P09](#p09) ↔ [P02](#p02) | `proposition-pair-fbc43713ba5067d64bc0f4ed67d0b4359ab8eb7c9d3224b32cb93bfd9fc90deb` | UNREVIEWED |
| [P09](#p09) ↔ [P03](#p03) | `proposition-pair-c8a8f6da3cffd7c939e417da00ca458e01de50d2f25b35b3e2075598ba1ef302` | UNREVIEWED |
| [P09](#p09) ↔ [P05](#p05) | `proposition-pair-983ac7546e8bfb0bcca11a5c34ce37bbfcfec9989f7e9b942148d8c78be08364` | UNREVIEWED |
| [P09](#p09) ↔ [P06](#p06) | `proposition-pair-7009257fe12b816fec772afd5d60dc25bb62d82b344d4702723755edb77b46dd` | UNREVIEWED |
| [P09](#p09) ↔ [P07](#p07) | `proposition-pair-229e4d10b7e3123e5aa474067ece90e3d7106139826041686398d635c9c75448` | UNREVIEWED |
| [P09](#p09) ↔ [P08](#p08) | `proposition-pair-aa44a330a226f46004ef4d02d1c78e161ca5898a73efe3da5da73a207687e8cc` | UNREVIEWED |

### 6.2 보고서 검증

모든 기술 요약은 §5.2의 승인된 원문과 CONTRIBUTION SemanticEvidence로 매핑했다. 인용 excerpt는 정확한 substring으로 확인했고, source span은 SourceUnit의 정확한 slice로 확인했다. 실제 raw ZIP member와 normalized artifact의 checksum을 확인했다. 모든 reviewed relation은 기존 양측 proposition에만 연결했다. 새로운 relation, 회사 입장, 회의 합의는 생성하지 않았다.

작성 전후 `data/`의 전체 파일 목록과 SHA-256을 비교하여 topic profile, source evidence, V0.12 review, V0.13 review 및 DuckDB가 바뀌지 않았음을 확인했다. 공식 문서 추가 취득은 0건이다. 이 Markdown 이외의 저장소 파일과 Git history는 변경하지 않았다.

집계: technical item 5개; 조직 이름 6개(공동 저자 집합 기준 5개); 본문 TDoc 6개; AcceptedProposition 10개; 기존 reviewed relation 12개; unreviewed comparison gap 27개; 미해결 source path 0개.
