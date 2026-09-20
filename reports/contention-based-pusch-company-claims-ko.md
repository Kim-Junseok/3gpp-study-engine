# Contention-based PUSCH 회사별 Contribution 주장 정리

## 1. 범위와 Evidence Coverage

> **이 문서는 현재 로컬에서 inspection이 완료된 contribution 범위만 요약한다. 미검사 TDoc의 회사 주장은 추론하지 않았다.**

분석 질문은 RAN1 #125–#126의 Contention-based PUSCH 관련 inspected contributions가 각 technical item에 대해 어떤 Proposal, Observation, Conclusion을 제시했는가이다. 기술 주장 분석의 1차 근거는 연구자가 승인한 70개 AcceptedProposition이다. 승인하지 않은 candidate를 주장 근거로 보충하지 않았다.

| Coverage 항목 | 수 |
|---|---:|
| Direct TDocs | 18 |
| Inspected TDocs | 14 |
| Uninspected / evidence-gap TDocs | 4 |
| Inspected TDocs with contribution SemanticEvidence | 9 |
| TDocs with AcceptedPropositions used | 8 |
| AcceptedPropositions used | 70 |
| Technical items | 8 |
| 기술 주장에 나타난 조직 메타데이터 이름 | 7 |
| Reviewed V0.13 relations referenced | 0 |

70개는 `accept` 69개와 `replace_with_exact_spans` 1개로 구성된다. 23개 defer와 29개 exclude_non_proposition은 기술 주장 근거로 사용하지 않았다. C080은 승인된 SourceUnit 문자 구간 `[0,171)`만 사용했다.

조직 이름 수 7은 Huawei와 HiSilicon을 각각 세며, 공동 제출 조합으로는 6개이다. 전체 direct inventory의 조직 이름은 16개다. 이 수들은 지지, 중요도, 합의 또는 독립적인 실험 증거의 수를 뜻하지 않는다.

근거 흐름은 **reviewed topic profile → direct TDoc inventory → CONTRIBUTION SemanticEvidence → AcceptedProposition**이다. AcceptedProposition은 연구자가 해당 원문 span을 보고·비교 단위로 승인했다는 뜻이다. 완전한 회사 입장, 기술적 진실, 회의 합의 또는 표준 채택을 뜻하지 않는다.

현재 direct corpus는 기존에 승인된 `contention based PUSCH`와 그 결정적 표기 정규화를 사용한다. 프로필에 이미 있던 `CBUL`, `contention-based uplink` seed와 formatting variant는 보존되어 있지만, 이번 direct TDoc association은 모두 승인된 `contention based PUSCH`에서 나온다. 이 보고서는 용어를 확장하지 않았다.

- Reviewed profile: `topic-profile-ec02cc4dd3694ce52753057429d1bc2a4902243a42830d1955de4d5ed9ec5b13` — [topic-profile.json](</home/jjuns/3gpp-study-engine/data/derived/topics/ran1/topic-profile-ec02cc4dd3694ce52753057429d1bc2a4902243a42830d1955de4d5ed9ec5b13/topic-profile.json>).
- Current inventory: `topic-inventory-29e5aa2721612abaf2962d36d4ee1f56eb4e8770c83fe33a3b4817f5b0d913f6`.
- Reviewed corpus: `topic-proposition-corpus-67df3b1343d1d578cb570965b53ea2a8d331f6bb547d56c443b7d8a07484cd97` — [corpus.json](</home/jjuns/3gpp-study-engine/data/derived/propositions/RAN1/topic-proposition-corpus-67df3b1343d1d578cb570965b53ea2a8d331f6bb547d56c443b7d8a07484cd97/corpus.json>).
- AcceptedPropositions: [accepted-propositions.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/propositions/RAN1/topic-proposition-corpus-67df3b1343d1d578cb570965b53ea2a8d331f6bb547d56c443b7d8a07484cd97/accepted-propositions.jsonl.gz>).
- Researcher reviews: [reviews.jsonl](</home/jjuns/3gpp-study-engine/data/derived/propositions/RAN1/topic-proposition-corpus-67df3b1343d1d578cb570965b53ea2a8d331f6bb547d56c443b7d8a07484cd97/reviews.jsonl>).

표의 C 번호는 원래 체크포인트의 로컬 별칭을 유지한 탐색용 표식이다. 각 번호는 아래 원문 확인 항목에서 전체 AcceptedProposition ID와 연결된다. 별칭 자체를 영속 identity로 사용하지 않는다.

동일 기술 내용의 반복 occurrence는 표시를 묶어도 모든 승인 ID와 EvidenceRef를 남긴다. 같은 조직의 여러 TDoc에서 반복된 문구도 별개의 지지 표로 세지 않는다. 서로 다른 EvidenceKind는 별도 행으로 유지한다. Technical item은 이 Markdown의 구성일 뿐 엔진 ontology나 formal proposition relation이 아니다.

## 2. 핵심 기술 쟁점 요약

| Technical item | 승인 원문에서 확인한 쟁점 | 근거 |
|---|---|---|
| 3.1 DMRS를 이용한 UE 식별과 port·sequence 선택 | vivo contribution은 식별·복호가 아직 연구 중인 UL DMRS 설계에 크게 의존한다고 서술했다. OPPO contribution은 port와 sequence에 따른 검출 차이를, Samsung contribution은 동일 DM-RS 선택 시 식별 실패를 관찰했다. | [C002](#ap-c002), [C027](#ap-c027), [C041](#ap-c041) |
| 3.2 Dedicated/shared DMRS와 multiplex 가능한 UE 수 | Ericsson contribution은 강한 상호 간섭 조건의 dedicated DMRS 수 제한과 shared DMRS의 충돌 확률 제한을 구분했다. Ofinno contribution은 기존 NR DM-RS 구성을 연구 출발점으로 서술하면서 blind detection 성능의 미검토를 함께 명시했다. | [C012](#ap-c012), [C013](#ap-c013), [C069](#ap-c069), [C070](#ap-c070) |
| 3.3 RNTI·payload UE ID와 blind decoding 복잡도 | Ericsson contribution은 dedicated DMRS·C-RNTI 구성과 shared DMRS·common RNTI·payload UE ID 구성을 나누어 서술했다. OPPO contribution은 지원하는 충돌 UE 수와 blind decoding 복잡도·검출 확률 사이의 경향을 관찰했다. | [C016](#ap-c016), [C017](#ap-c017), [C028](#ap-c028) |
| 3.4 충돌한 payload의 복호 조건과 BLER | Ericsson contribution은 강하지 않은 상호 간섭에서의 복호 가능성과 shared DMRS 확장을 통한 BLER 억제를 서술했다. Samsung contribution은 MMSE IRC 수신기와 낮은 트래픽 도착률이라는 조건을 명시했고, Huawei/HiSilicon contribution은 DMRS 충돌뿐 아니라 port/layer 간 간섭을 고려하도록 제시했다. | [C014](#ap-c014), [C015](#ap-c015), [C042](#ap-c042), [C048](#ap-c048), [C084](#ap-c084) |
| 3.5 Initial transmission·reattempt와 random backoff | Ericsson의 #126 문서는 초기 충돌 복호와 재시도를 구분했다. R1-2605343의 Observation은 일반적으로 절반 미만, R1-2606780은 일반적으로 약 40%를 서술하며, 재시도에서는 낮은 residual BLER와 backoff 불필요 가능성을 연결했다. | [C096](#ap-c096), [C113](#ap-c113), [C097](#ap-c097), [C114](#ap-c114) |
| 3.6 Early BSR의 효용, 트래픽 부하와 CG-PUSCH 운용 조건 | Samsung contribution은 early BSR의 효용을 부하·작은 TB·첫 송신 조건으로 제한했다. 또한 평가 초점과 CG-PUSCH에 대한 운용상 문제를 각각 Observation으로 제시했다. | [C044](#ap-c044), [C046](#ap-c046), [C050](#ap-c050) |
| 3.7 평가 가정: 시간 자원·채널 상관·DMRS 외 충돌 완화 | Huawei/HiSilicon contribution은 슬롯 내 시간 자원 가정, UL MU-MIMO 채널 상관 모델과 UE dedicated preamble을 언급했다. Samsung contribution은 식별·복호의 상세 평가 가정을, Ericsson contribution은 각 TDoc의 Table 1을 이용한 시뮬레이션 출발점을 제시했다. | [C080](#ap-c080), [C086](#ap-c086), [C087](#ap-c087), [C039](#ap-c039), [C022](#ap-c022) |
| 3.8 추가 연구의 범위와 RAN2 회신 시점 | vivo contribution은 추가 연구 후보와 평가 가정·규격 영향을 RAN2에 알리는 내용을 제안했다. Huawei/HiSilicon의 conclusion은 PUSCH·DMRS 가정과 평가 관찰이 합의될 때까지 충돌 관련 회신을 미루는 내용을 제시했다. | [C003](#ap-c003), [C004](#ap-c004), [C088](#ap-c088) |

아래 내용은 각 contribution의 명시적 주장이다. **이 회사 간 proposition relation은 아직 V0.13 review되지 않았다.** 같은 기술 질문 아래 배치되었다는 사실만으로 proposition 간 일치·차이·충돌이나 회사 간 합의를 판정하지 않는다.

## 3. Technical Item별 회사 주장

<a id="item-1"></a>

### 3.1 DMRS를 이용한 UE 식별과 port·sequence 선택

#### 기술 질문

충돌한 contention-based PUSCH에서 UE를 식별할 때 어떤 DMRS 설계와 식별 조건을 검토하는가?

#### 회사별 Contribution

| 회사/조직 | TDoc | Meeting | Kind | 한글 요약 | EvidenceRef |
|---|---|---|---|---|---|
| vivo | R1-2603620 | RAN1 #125 | OBSERVATION | vivo의 해당 Observation은 여러 UE의 송신이 충돌한 contention-based PUSCH에서 네트워크의 UE 구분과 payload 복호가, RAN1에서 아직 연구 중인 UL DMRS 설계에 크게 의존한다고 관찰했다. | [C002](#ap-c002) `R1-2603620/b000029` |
| vivo | R1-2603620 | RAN1 #125 | PROPOSAL | vivo의 해당 Proposal은 UL DMRS 설계가 명확해지는 이후 단계에 contention-based PUSCH의 UE 구분 질문에 답하겠다고 RAN2에 알리는 방안을 제안했다. | [C005](#ap-c005) `R1-2603620/b000035` |
| Ericsson | R1-2603673<br>R1-2605343<br>R1-2606780 | RAN1 #125<br>RAN1 #126 | PROPOSAL | Ericsson의 각 Proposal은 여러 UE가 같은 시간·주파수 자원을 선택하더라도 서로 다른 DMRS port 및/또는 scrambling sequence를 사용하면 네트워크가 payload를 복호하고 UE를 구분할 수 있다는 내용을 RAN2에 전달하는 방안을 제안했다. | [C018](#ap-c018) `R1-2603673/b000038`<br>[C098](#ap-c098) `R1-2605343/b000045`<br>[C115](#ap-c115) `R1-2606780/b000046` |
| OPPO | R1-2604097 | RAN1 #125 | OBSERVATION | OPPO contribution은 DMRS가 다중 사용자 직교성을 구현하는 전형적이고 가장 구현 가능한 방법이라고 관찰했다. DMRS에 전혀 의존하지 않는 직교화 방식은 유의미한 성능·구현 이점을 주지 못할 수 있다고 서술했다. | [C026](#ap-c026) `R1-2604097/b000016` |
| OPPO | R1-2604097 | RAN1 #125 | OBSERVATION | OPPO contribution은 UE별 채널 상태에 따라, 서로 다른 DMRS port를 사용할 때 충돌한 PUSCH의 검출 확률이 서로 다른 DMRS sequence를 사용할 때보다 높다고 관찰했다. | [C027](#ap-c027) `R1-2604097/b000038` |
| Samsung | R1-2604147 | RAN1 #125 | OBSERVATION | Samsung contribution은 PUSCH DM-RS 기반 식별이 1-bit SR PUCCH 기반 식별보다 상당히 열악하다고 관찰했다. 성능 차이의 구체적인 수치나 평가 조건은 이 승인 문장에 명시되어 있지 않다. | [C037](#ap-c037) `R1-2604147/b000022` |
| Samsung | R1-2604147 | RAN1 #125 | OBSERVATION | Samsung contribution은 적어도 두 UE가 같은 DM-RS를 선택하면 DM-RS 기반 식별이 실패한다고 관찰했다. | [C041](#ap-c041) `R1-2604147/b000026` |
| Huawei, HiSilicon | R1-2604920 | RAN1 #125 | CONCLUSION | Huawei/HiSilicon의 해당 contribution의 conclusion에서는 필요한 직교·비직교 DMRS port 수와 DMRS port–UE 연결 관계를 RAN1에서 논의해야 한다는 내용을 제시했다. | [C085](#ap-c085) `R1-2604920/b000050` |

#### 해석 메모

같은 절에 배치한 것은 UE 식별이라는 질문을 공유하기 때문이다. port·sequence·식별 방식에 대한 각 TDoc의 서술을 독립적으로 읽어야 한다. 여기서 DMRS 검출, UE 식별, payload 복호를 동일한 성공 사건으로 간주하지 않는다.

#### 원문 확인

아래는 이 절에 사용한 승인 span의 원문이다. 문자열이 정확히 같은 승인 span은 한 번 인용하고 모든 TDoc·승인 번호를 함께 표시했다. 전체 ID·member·EvidenceRef는 [5절의 proposition별 provenance](#proposition-provenance)에서 확인할 수 있다.

[C002](#ap-c002) — R1-2603620:

```text
Observation 2: The network's ability to differentiate UEs and decode the payload in a contention-based PUSCH resource with collided transmissions from multiple UEs is highly dependent on the UL DMRS design, which is still under study in RAN1.
```

[C005](#ap-c005) — R1-2603620:

```text
Proposal 3: RAN1 informs RAN2 that the questions related to differentiating UE in a contention based PUSCH will be answered at later stage when RAN1 UL DMRS design becomes clear.
```

[C018](#ap-c018), [C098](#ap-c098), [C115](#ap-c115) — R1-2603673, R1-2605343, R1-2606780:

```text
Proposal 1RAN1 informs RAN2 of the following: When multiple UEs select the same time–frequency resource, the network can decode the payload and distinguish the UEs using different DMRS ports and/or scrambling sequences.
```

[C026](#ap-c026) — R1-2604097:

```text
Observation 1: Utilizing DMRS is the typical and most implementable method to realize multi-user orthogonality, and any multi-user orthogonality scheme that completely does not rely on DMRS may not bring any meaningful performance or implementation advantages.
```

[C027](#ap-c027) — R1-2604097:

```text
Observation 2: For different DMRS port, the detection probably of colliding PUSCHs is higher than that of different DMRS sequence, depending on the channel status of each UE.
```

[C037](#ap-c037) — R1-2604147:

```text
PUSCH DM-RS based identification is substantially worse than 1-bit SR PUCCH based identification.
```

[C041](#ap-c041) — R1-2604147:

```text
DM-RS based identification would fail when at least two UEs choose the same DM-RS.
```

[C085](#ap-c085) — R1-2604920:

```text
RAN1 needs to discuss the number of orthogonal and non-orthogonal ports required for DMRS and the association between a DMRS port and a UE.
```

원문 문서: R1-2603620: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603620/R1-2603620.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603620/document.jsonl.gz>); R1-2603673: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603673/R1-2603673.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603673/document.jsonl.gz>); R1-2604097: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604097/R1-2604097.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604097/document.jsonl.gz>); R1-2604147: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604147/R1-2604147.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604147/document.jsonl.gz>); R1-2604920: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604920/R1-2604920.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604920/document.jsonl.gz>); R1-2605343: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2605343/R1-2605343.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2605343/document.jsonl.gz>); R1-2606780: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2606780/R1-2606780.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2606780/document.jsonl.gz>)

<a id="item-2"></a>

### 3.2 Dedicated/shared DMRS와 multiplex 가능한 UE 수

#### 기술 질문

DMRS를 UE에 전용으로 배정하거나 공유할 때 UE 수를 제한하는 조건은 무엇이며, 기존 NR 구조를 어떤 연구 출발점으로 보는가?

#### 회사별 Contribution

| 회사/조직 | TDoc | Meeting | Kind | 한글 요약 | EvidenceRef |
|---|---|---|---|---|---|
| Ericsson | R1-2603673<br>R1-2605343<br>R1-2606780 | RAN1 #125<br>RAN1 #126 | OBSERVATION | Ericsson의 각 Observation은 서로 강하게 간섭하는 UE에 서로 다른 N개 DMRS를 dedicated로 배정하면 같은 시간·주파수 자원에서 최대 N개 UE를 multiplex할 수 있다고 관찰했다. DMRS를 공유하면 UE 수의 상한이 DMRS 충돌 확률에 의해 제한되므로 N보다 훨씬 많은 UE를 multiplex할 수 있다고 서술했다. | [C012](#ap-c012) `R1-2603673/b000034`<br>[C013](#ap-c013) `R1-2603673/b000034`<br>[C090](#ap-c090) `R1-2605343/b000040`<br>[C091](#ap-c091) `R1-2605343/b000040`<br>[C107](#ap-c107) `R1-2606780/b000041`<br>[C108](#ap-c108) `R1-2606780/b000041` |
| Ericsson | R1-2603673<br>R1-2605343<br>R1-2606780 | RAN1 #125<br>RAN1 #126 | PROPOSAL | Ericsson의 각 Proposal은 N개 DMRS를 dedicated로 배정하면 자원에서 최대 N개 UE를 multiplex하고, shared DMRS에서는 충돌 확률이 제한 요인이 된다는 내용을 제안 내용으로 제시했다. | [C020](#ap-c020) `R1-2603673/b000038`<br>[C100](#ap-c100) `R1-2605343/b000045`<br>[C117](#ap-c117) `R1-2606780/b000046` |
| Ofinno | R1-2604209 | RAN1 #125 | OBSERVATION | Ofinno contribution은 NR이 연계된 preamble 송신 없이 contention-based PUSCH를 지원하지 않는다고 관찰했다. 이어 초기 분석에서 preamble 없는 MsgA PUSCH 또는 configured-grant PUSCH 같은 NR 기능을 검토할 수 있다고 서술했다. 이 표현은 원문의 분석 출발점 서술로 보존한다. | [C067](#ap-c067) `R1-2604209/b000015`<br>[C068](#ap-c068) `R1-2604209/b000015` |
| Ofinno | R1-2604209 | RAN1 #125 | OBSERVATION | Ofinno contribution은 같은 시간·주파수 자원에서 MsgA PUSCH가 최대 4개의 직교 DM-RS와 잠재적으로 4개 UE를, CG PUSCH가 최대 24개의 직교 DM-RS와 일부 제한에 따른 14개 UE를 지원한다고 관찰했다. 이를 연구 출발점으로 삼을 수 있지만 해당 직교 DM-RS의 blind detection 성능은 RAN1에서 연구되지 않아 당시 RAN2 Q1에 명확한 답이 없다고 함께 서술했다. | [C069](#ap-c069) `R1-2604209/b000022`<br>[C070](#ap-c070) `R1-2604209/b000022` |

#### 해석 메모

N은 해당 Ericsson 문장에 등장하는 DMRS 수다. Ofinno의 4·24·14 수치는 그 contribution의 서술이며, 이 보고서가 표준 원문을 별도로 검증한 수치가 아니다. 물리적으로 배치 가능한 직교 DM-RS 수와 blind detection 성능을 동일시하지 않는다.

#### 원문 확인

아래는 이 절에 사용한 승인 span의 원문이다. 문자열이 정확히 같은 승인 span은 한 번 인용하고 모든 TDoc·승인 번호를 함께 표시했다. 전체 ID·member·EvidenceRef는 [5절의 proposition별 provenance](#proposition-provenance)에서 확인할 수 있다.

[C012](#ap-c012), [C090](#ap-c090), [C107](#ap-c107) — R1-2603673, R1-2605343, R1-2606780:

```text
Observation 1If N distinct DMRS are dedicated to UEs, at most N UEs can be multiplexed in the same time frequency resources when they strongly interfere.
```

[C013](#ap-c013), [C091](#ap-c091), [C108](#ap-c108) — R1-2603673, R1-2605343, R1-2606780:

```text
If the DMRS are shared, many more than N UEs can be multiplexed, since the upper limit number of UEs is instead limited by the probability of DMRS collision.
```

[C020](#ap-c020), [C100](#ap-c100), [C117](#ap-c117) — R1-2603673, R1-2605343, R1-2606780:

```text
If N DMRSs are dedicated to UEs, at most N UEs can be multiplexed in the resource, while if DMRSs are shared, the probability of collision is the limiting factor.
```

[C067](#ap-c067) — R1-2604209:

```text
Observation 1: NR does not support a contention-based PUSCH without associated preamble transmission.
```

[C068](#ap-c068) — R1-2604209:

```text
For an initial analysis, supported NR features such as MsgA PUSCH without preamble or configured grant PUSCH could be considered.
```

[C069](#ap-c069) — R1-2604209:

```text
Observation 2: NR design supports up to 4 orthogonal DM-RS (and thus potentially 4 UEs) for MsgA PUSCH or up to 24 orthogonal DM-RSs (based on some limitation, leading to 14 UEs) for CG PUSCH on the same time/frequency resource.
```

[C070](#ap-c070) — R1-2604209:

```text
Though these can be a starting point of study, it should be noted that performance of blind detection on such orthogonal DM-RS design are not studied in RAN1, and thus RAN1 does not have a clear answer on Q1 from RAN2 at this moment.
```

원문 문서: R1-2603673: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603673/R1-2603673.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603673/document.jsonl.gz>); R1-2604209: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604209/R1-2604209.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604209/document.jsonl.gz>); R1-2605343: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2605343/R1-2605343.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2605343/document.jsonl.gz>); R1-2606780: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2606780/R1-2606780.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2606780/document.jsonl.gz>)

<a id="item-3"></a>

### 3.3 RNTI·payload UE ID와 blind decoding 복잡도

#### 기술 질문

DMRS와 RNTI의 조합 및 payload 내 UE ID가 blind decoding 횟수와 UE 식별에 어떤 영향을 준다고 서술하는가?

#### 회사별 Contribution

| 회사/조직 | TDoc | Meeting | Kind | 한글 요약 | EvidenceRef |
|---|---|---|---|---|---|
| Ericsson | R1-2603673 | RAN1 #125 | OBSERVATION | Ericsson의 R1-2603673에서는 같은 시간·주파수 자원에 CB-BSR을 보내는 UE가 N개 dedicated DMRS와 C-RNTI를 사용하면 네트워크에 N회의 복호가 필요하고 DMRS 직교성에 일부 제한이 생긴다고 관찰했다. | [C016](#ap-c016) `R1-2603673/b000037` |
| Ericsson | R1-2605343<br>R1-2606780 | RAN1 #126 | OBSERVATION | Ericsson의 두 #126 contribution에서는 N개 dedicated DMRS와 C-RNTI로 같은 시간·주파수 자원에 CB-BSR을 보내면 N회의 복호가 필요하며, 서로 다른 scrambling 사용이 DMRS 직교성을 제한한다고 관찰했다. | [C094](#ap-c094) `R1-2605343/b000043`<br>[C111](#ap-c111) `R1-2606780/b000044` |
| Ericsson | R1-2603673<br>R1-2605343<br>R1-2606780 | RAN1 #125<br>RAN1 #126 | OBSERVATION | Ericsson의 각 Observation은 M개 UE가 N개 shared DMRS와 common RNTI를 사용하고 payload에 UE ID를 실으면 여전히 N회의 blind decoding이 필요하지만, M≫N개의 UE가 자원을 공유할 수 있고 내재적인 DMRS 직교성 손실은 없다고 관찰했다. | [C017](#ap-c017) `R1-2603673/b000037`<br>[C095](#ap-c095) `R1-2605343/b000043`<br>[C112](#ap-c112) `R1-2606780/b000044` |
| Ericsson | R1-2603673<br>R1-2605343<br>R1-2606780 | RAN1 #125<br>RAN1 #126 | PROPOSAL | Ericsson의 각 Proposal은 해당 자원에서 필요한 aNB의 blind decoding 횟수가 사용한 DMRS 수 × RNTI 수에 비례해 증가한다는 내용을 제안 내용으로 제시했다. | [C019](#ap-c019) `R1-2603673/b000038`<br>[C099](#ap-c099) `R1-2605343/b000045`<br>[C116](#ap-c116) `R1-2606780/b000046` |
| Ericsson | R1-2603673<br>R1-2605343<br>R1-2606780 | RAN1 #125<br>RAN1 #126 | PROPOSAL | Ericsson의 각 Proposal은 CB-BSR payload에 UE ID를 실으면 N개 DMRS를 공유하는 UE를, 동일한 DMRS를 갖는 UE까지 포함하여 식별할 수 있다는 내용을 제안 내용으로 제시했다. | [C021](#ap-c021) `R1-2603673/b000038`<br>[C101](#ap-c101) `R1-2605343/b000045`<br>[C118](#ap-c118) `R1-2606780/b000046` |
| OPPO | R1-2604097 | RAN1 #125 | OBSERVATION | OPPO contribution은 해당 분석에서 지원하는 충돌 UE 수가 늘수록 blind decoding 복잡도가 증가하고 검출 확률은 낮아지는 경향이 있다고 관찰했다. 원문이 언급하는 표의 세부 수치는 이 승인 문장만으로 보충하지 않았다. | [C028](#ap-c028) `R1-2604097/b000039` |

#### 해석 메모

Blind decoding 횟수, 식별 가능한 UE 수, payload 검출 확률은 서로 다른 항목으로 읽는다. Payload에 UE ID를 넣는다는 문장만으로 충돌한 payload의 복호 성공을 확정하지 않는다. #125와 #126에서 scrambling 관련 표현이 다른 부분은 아래 행에 따로 남겼다.

#### 원문 확인

아래는 이 절에 사용한 승인 span의 원문이다. 문자열이 정확히 같은 승인 span은 한 번 인용하고 모든 TDoc·승인 번호를 함께 표시했다. 전체 ID·member·EvidenceRef는 [5절의 proposition별 provenance](#proposition-provenance)에서 확인할 수 있다.

[C016](#ap-c016) — R1-2603673:

```text
Observation 4If N dedicated DMRS and C-RNTIs are used by UEs transmitting CB-BSR in a same time/frequency resource, the network will need to decode N times, and there will be some limitations on DMRS orthogonality.
```

[C094](#ap-c094), [C111](#ap-c111) — R1-2605343, R1-2606780:

```text
Observation 4If N dedicated DMRS and C-RNTIs are used by UEs transmitting CB-BSR in a same time/frequency resource, the network will need to decode N times, and DMRS orthogonality will be limited by the use of different scrambling.
```

[C017](#ap-c017), [C095](#ap-c095), [C112](#ap-c112) — R1-2603673, R1-2605343, R1-2606780:

```text
If M UEs use a common RNTI with N shared DMRS and carry a UE ID in their payload, the network will still blindly decode N times, but M>>N UEs can share the resource and there is no inherent DMRS orthogonality loss.
```

[C019](#ap-c019), [C099](#ap-c099), [C116](#ap-c116) — R1-2603673, R1-2605343, R1-2606780:

```text
The number of blind decodes needed by the aNB for the resource increases in proportion to the number of DMRSs x RNTIs used with the resource.
```

[C021](#ap-c021), [C101](#ap-c101), [C118](#ap-c118) — R1-2603673, R1-2605343, R1-2606780:

```text
If a UE ID is carried in the CB-BSR payload, UEs sharing the N DMRSs, including those that have identical DMRSs, can still be identified.
```

[C028](#ap-c028) — R1-2604097:

```text
Observation 3: Based on the systematic analysis above, RAN1 clarifies that for CB-PUSCH collision scenarios, there exists a clear trend that as the supported colliding UE increases, the blind decoding complexity rises while the detection probability degrades, listed in the table below.
```

원문 문서: R1-2603673: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603673/R1-2603673.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603673/document.jsonl.gz>); R1-2604097: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604097/R1-2604097.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604097/document.jsonl.gz>); R1-2605343: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2605343/R1-2605343.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2605343/document.jsonl.gz>); R1-2606780: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2606780/R1-2606780.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2606780/document.jsonl.gz>)

<a id="item-4"></a>

### 3.4 충돌한 payload의 복호 조건과 BLER

#### 기술 질문

동일 DMRS 또는 PUSCH 자원 충돌에서 간섭·수신기·트래픽 조건에 따라 payload 복호 가능성을 어떻게 서술하는가?

#### 회사별 Contribution

| 회사/조직 | TDoc | Meeting | Kind | 한글 요약 | EvidenceRef |
|---|---|---|---|---|---|
| Ericsson | R1-2603673<br>R1-2605343<br>R1-2606780 | RAN1 #125<br>RAN1 #126 | OBSERVATION | Ericsson의 각 Observation은 UE들이 서로 강하게 간섭하지 않는 경우, 예를 들어 한 UE의 수신 전력이 다른 UE보다 높은 경우에는 같은 DMRS와 같은 시간·주파수 자원을 선택해도 하나 이상의 UE 송신을 복호할 수 있다고 관찰했다. | [C014](#ap-c014) `R1-2603673/b000035`<br>[C092](#ap-c092) `R1-2605343/b000041`<br>[C109](#ap-c109) `R1-2606780/b000042` |
| Ericsson | R1-2603673 | RAN1 #125 | OBSERVATION | Ericsson의 R1-2603673에서는 shared DMRS port 및/또는 scrambling sequence를 더 배정하면 contention-based 동작의 과도한 BLER를 피할 수 있다고 관찰했다. | [C015](#ap-c015) `R1-2603673/b000036` |
| Ericsson | R1-2605343<br>R1-2606780 | RAN1 #126 | OBSERVATION | Ericsson의 두 #126 contribution에서는 다중 안테나 aNB 수신을 전제로 shared DMRS port 및/또는 scrambling sequence를 더 배정하면 과도한 BLER를 피할 수 있다고 관찰했다. | [C093](#ap-c093) `R1-2605343/b000042`<br>[C110](#ap-c110) `R1-2606780/b000043` |
| Samsung | R1-2604147 | RAN1 #125 | OBSERVATION | Samsung contribution은 적어도 두 UE가 같은 PUSCH 자원을 선택하면 DM-RS port/sequence의 직교 여부와 무관하게 MMSE IRC 수신기 기반 PUSCH 복호가 실패할 것으로 예상한다고 관찰했다. | [C042](#ap-c042) `R1-2604147/b000026` |
| Samsung | R1-2604147 | RAN1 #125 | OBSERVATION | Samsung contribution은 트래픽 도착률이 매우 낮지 않으면, genie가 DM-RS 존재 여부를 알려 주는 이상적인 조건에서도 DM-RS 식별 또는 올바른 contention-based PUSCH 복호가 실패한다고 관찰했다. 매우 낮은 도착률의 예로 UE당 초당 1 BSR, 36개 UE, 2.5 ms 송신 기회에서 BSR이 없을 확률 90% 초과를 들었다. | [C048](#ap-c048) `R1-2604147/b000043` |
| Huawei, HiSilicon | R1-2604920 | RAN1 #125 | CONCLUSION | Huawei/HiSilicon의 해당 contribution의 conclusion에서는 충돌한 payload의 복호 확률을 볼 때 DMRS 충돌 확률과 PUSCH의 port/layer 간 간섭을 고려해야 한다고 제시했다. 직교 DMRS port를 사용해도 후자의 간섭을 고려해야 한다는 조건을 보존한다. | [C084](#ap-c084) `R1-2604920/b000049` |

#### 해석 메모

각 문장의 수신기·간섭·트래픽 조건을 제거하면 의미가 달라진다. 서로 다른 조건을 기술한 문장을 회사 간 모순이나 합의로 판정하지 않는다. 아래 수치와 실패·복호 가능성은 각각의 contribution이 제시한 관찰이다.

#### 원문 확인

아래는 이 절에 사용한 승인 span의 원문이다. 문자열이 정확히 같은 승인 span은 한 번 인용하고 모든 TDoc·승인 번호를 함께 표시했다. 전체 ID·member·EvidenceRef는 [5절의 proposition별 provenance](#proposition-provenance)에서 확인할 수 있다.

[C014](#ap-c014), [C092](#ap-c092), [C109](#ap-c109) — R1-2603673, R1-2605343, R1-2606780:

```text
Observation 2If UEs do not strongly interfere,  e.g., one user received at higher power than another, it is possible that one or more UEs’ transmissions can be decoded even when the same DMRS are selected and the UEs use the same time/frequency resources.
```

[C015](#ap-c015) — R1-2603673:

```text
Observation 3From RAN1 perspective, contention-based operation can avoid excessive BLER by allocating more shared DMRS ports and/or scrambling sequences.
```

[C093](#ap-c093), [C110](#ap-c110) — R1-2605343, R1-2606780:

```text
Observation 3From RAN1 perspective, contention-based operation can avoid excessive BLER given multi-antenna aNB reception and by allocating more shared DMRS ports and/or scrambling sequences.
```

[C042](#ap-c042) — R1-2604147:

```text
Also, PUSCH decoding based on MMSE IRC receiver is expected to fail when at least two UEs choose same PUSCH resources regardless of whether or not the UEs choose orthogonal DM-RS ports/sequences.
```

[C048](#ap-c048) — R1-2604147:

```text
Unless the traffic arrival rate is very low, such as 1 BSR per UE per second resulting in over 90% probability of no BSR at a transmission occasion over 2.5 msec from 36 UEs, DM-RS identification or correct decoding for contention-based PUSCH fails even under ideal conditions (genie determines presence/absence of DM-RS).
```

[C084](#ap-c084) — R1-2604920:

```text
From RAN1 perspective the probability of decoding a colliding payload should consider DMRS collision probability, and cross-port/layer interference on PUSCH even if orthogonal DMRS ports are used.
```

원문 문서: R1-2603673: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603673/R1-2603673.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603673/document.jsonl.gz>); R1-2604147: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604147/R1-2604147.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604147/document.jsonl.gz>); R1-2604920: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604920/R1-2604920.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604920/document.jsonl.gz>); R1-2605343: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2605343/R1-2605343.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2605343/document.jsonl.gz>); R1-2606780: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2606780/R1-2606780.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2606780/document.jsonl.gz>)

<a id="item-5"></a>

### 3.5 Initial transmission·reattempt와 random backoff

#### 기술 질문

충돌한 CB-BSR의 초기 송신과 재시도 성공률을 어떻게 구분하며, random backoff 필요성은 어떤 조건에서 논의하는가?

#### 회사별 Contribution

| 회사/조직 | TDoc | Meeting | Kind | 한글 요약 | EvidenceRef |
|---|---|---|---|---|---|
| Ericsson | R1-2605343 | RAN1 #126 | OBSERVATION | Ericsson의 R1-2605343에서는 CB-BSR 자원에서 충돌한 UE 송신도 성공적으로 복호될 수 있지만, 일반적으로 그 비율이 절반 미만이라고 관찰했다. | [C096](#ap-c096) `R1-2605343/b000044` |
| Ericsson | R1-2606780 | RAN1 #126 | OBSERVATION | Ericsson의 R1-2606780에서는 CB-BSR 자원에서 충돌한 UE 송신도 성공적으로 복호될 수 있지만, 일반적으로 그 비율이 약 40%라고 관찰했다. | [C113](#ap-c113) `R1-2606780/b000045` |
| Ericsson | R1-2605343<br>R1-2606780 | RAN1 #126 | OBSERVATION | Ericsson의 두 #126 contribution은 재시도를 사용하면 처음에 충돌한 UE도 낮은 residual BLER로 복호할 수 있으며, 이로부터 random backoff가 필요하지 않을 것이라는 해석을 해당 Observation에 제시했다. | [C097](#ap-c097) `R1-2605343/b000044`<br>[C114](#ap-c114) `R1-2606780/b000045` |
| Ericsson | R1-2605343<br>R1-2606780 | RAN1 #126 | PROPOSAL | Ericsson의 두 #126 Proposal은 시스템 수준에서 같은 DMRS port와 sequence로 동시에 송신한 UE도 복호할 수 있으나 CB-BSR 초기 송신 성공률은 절반 미만일 수 있고, 재시도를 사용하면 1에 근접하는 성공률이 가능하다는 내용을 RAN2에 전달하는 방안을 제안했다. | [C102](#ap-c102) `R1-2605343/b000046`<br>[C103](#ap-c103) `R1-2605343/b000046`<br>[C119](#ap-c119) `R1-2606780/b000047`<br>[C120](#ap-c120) `R1-2606780/b000047` |

#### 해석 메모

“일반적으로 절반 미만”과 “일반적으로 약 40%”를 하나의 수치로 바꾸지 않는다. 재시도에 관한 낮은 residual BLER와 성공률 1에 근접할 수 있다는 서술을 모든 부하·수신기에서의 보장으로 일반화하지 않는다. 여기서 두 TDoc 사이의 진화나 formal relation을 추론하지 않는다.

#### 원문 확인

아래는 이 절에 사용한 승인 span의 원문이다. 문자열이 정확히 같은 승인 span은 한 번 인용하고 모든 TDoc·승인 번호를 함께 표시했다. 전체 ID·member·EvidenceRef는 [5절의 proposition별 provenance](#proposition-provenance)에서 확인할 수 있다.

[C096](#ap-c096) — R1-2605343:

```text
Observation 5UEs colliding and in CB-BSR resource can be successfully decoded, but generally less than half of the time.
```

[C113](#ap-c113) — R1-2606780:

```text
Observation 5UEs colliding and in CB-BSR resource can be successfully decoded, but generally around 40% of the time.
```

[C097](#ap-c097), [C114](#ap-c114) — R1-2605343, R1-2606780:

```text
If reattempts are used, UEs that initially collide can be decoded with low residual BLER, which implies that random backoffs would not be needed.
```

[C102](#ap-c102), [C119](#ap-c119) — R1-2605343, R1-2606780:

```text
Proposal 2Inform RAN2 that from a system level perspective: 1) Simultaneously transmitting UEs using the same DMRS ports and sequence can be decoded successfully, but the success rate may be less than half the time for an initial transmission of a CB-BSR.
```

[C103](#ap-c103), [C120](#ap-c120) — R1-2605343, R1-2606780:

```text
2) When reattempts are used, success rates approaching 1 are possible.
```

원문 문서: R1-2605343: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2605343/R1-2605343.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2605343/document.jsonl.gz>); R1-2606780: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2606780/R1-2606780.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2606780/document.jsonl.gz>)

<a id="item-6"></a>

### 3.6 Early BSR의 효용, 트래픽 부하와 CG-PUSCH 운용 조건

#### 기술 질문

Early BSR의 유용성을 어떤 부하·TB·송신 조건으로 제한하며, 필수 자원 요청 기능에 적용하기 전 어떤 운용 문제를 제시하는가?

#### 회사별 Contribution

| 회사/조직 | TDoc | Meeting | Kind | 한글 요약 | EvidenceRef |
|---|---|---|---|---|---|
| Samsung | R1-2604147 | RAN1 #125 | OBSERVATION | Samsung contribution은 early BSR이 낮거나 중간인 시스템 부하에서는 실질적으로 쓸모없고, 작은 TB 같은 높은 시스템 부하 조건에서 첫 송신에만 이점을 줄 수 있으며, 다른 애플리케이션·시나리오에서는 throughput을 개선하지 않는다고 관찰했다. | [C044](#ap-c044) `R1-2604147/b000033` |
| Samsung | R1-2604147 | RAN1 #125 | OBSERVATION | Samsung contribution은 높은 시스템 부하와 작은 TB를 갖는 애플리케이션의 트래픽 도착률에 평가 초점을 둘 수 있다는 내용을 Observation으로 제시했다. | [C046](#ap-c046) `R1-2604147/b000034` |
| Samsung | R1-2604147 | RAN1 #125 | OBSERVATION | Samsung contribution은 자원 낭비, false alarm으로 인한 HARQ 손상, 존재하지 않는 TB에 대한 불필요한 aNB 복호를 CG-PUSCH의 상용 LTE·NR 적용을 막아 온 문제로 서술했다. 이 문제들이 해결되지 않으면 데이터 송신을 위한 UE 요청 같은 필수 기능을 지원하도록 aNB에 CG-PUSCH를 요구하는 것은 피해야 한다는 내용을 Observation으로 제시했다. | [C050](#ap-c050) `R1-2604147/b000047` |

#### 해석 메모

이 절의 승인 근거는 Samsung의 해당 TDoc에 한정된다. 다른 회사의 근거가 이 절에 없다는 사실로 다른 회사의 입장이나 기술적 관심을 추론하지 않는다. 평가 초점에 관한 C046도 원래 EvidenceKind인 OBSERVATION으로 유지했다.

#### 원문 확인

아래는 이 절에 사용한 승인 span의 원문이다. 문자열이 정확히 같은 승인 span은 한 번 인용하고 모든 TDoc·승인 번호를 함께 표시했다. 전체 ID·member·EvidenceRef는 [5절의 proposition별 provenance](#proposition-provenance)에서 확인할 수 있다.

[C044](#ap-c044) — R1-2604147:

```text
Early BSR report is practically useless for low/medium system loads, may only benefit a first transmission for high system loads such as for small TBs, and does not improve throughput for other applications/scenarios.
```

[C046](#ap-c046) — R1-2604147:

```text
Evaluations may focus on high system loads and traffic arrival rates associated with applications having small TBs.
```

[C050](#ap-c050) — R1-2604147:

```text
Unless the issues that have prevented CG-PUSCH from being deployed in commercial LTE and NR (resource waste, false alarms causing HARQ corruption, and unnecessary aNB decoding for non-existing TBs) are resolved, requiring CG-PUSCH at the aNB to support an essential function such as a UE request to transmit data should be avoided
```

원문 문서: R1-2604147: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604147/R1-2604147.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604147/document.jsonl.gz>)

<a id="item-7"></a>

### 3.7 평가 가정: 시간 자원·채널 상관·DMRS 외 충돌 완화

#### 기술 질문

평가를 시작하기 전에 시간 자원, 채널 모델, 식별·복호 조건과 대안 메커니즘을 어떻게 구체화해야 한다고 제시하는가?

#### 회사별 Contribution

| 회사/조직 | TDoc | Meeting | Kind | 한글 요약 | EvidenceRef |
|---|---|---|---|---|---|
| Samsung | R1-2604147 | RAN1 #125 | PROPOSAL | Samsung의 해당 Proposal은 DM-RS 식별과 payload 복호를 위한 상세 평가 가정을 RAN1이 논의하고 정의하는 방안을 제안했다. | [C039](#ap-c039) `R1-2604147/b000024` |
| Huawei, HiSilicon | R1-2604920 | RAN1 #125 | CONCLUSION | Huawei/HiSilicon의 해당 contribution의 conclusion에서는 agenda item 10.5.2.3의 일반 PUSCH 연구 진척을 고려하여, 슬롯 내 CB-PUSCH 시간 영역 할당 가정을 먼저 논의해야 한다고 제시했다. | [C080](#ap-c080) `R1-2604920/b000045` |
| Huawei, HiSilicon | R1-2604920 | RAN1 #125 | CONCLUSION | Huawei/HiSilicon의 해당 contribution의 conclusion에서는 CB-PUSCH를 사용하는 UL MU-MIMO의 채널 상관 모델링을 RAN1이 논의해야 한다고 제시했다. | [C086](#ap-c086) `R1-2604920/b000051` |
| Huawei, HiSilicon | R1-2604920 | RAN1 #125 | CONCLUSION | Huawei/HiSilicon의 해당 contribution의 conclusion에서는 shared/non-orthogonal 자원에서 잠재적 충돌을 줄이거나 완화하기 위해, DMRS 설계 외에도 UE dedicated preamble 같은 방법이 RAN1에서 여전히 논의 중이라고 서술했다. | [C087](#ap-c087) `R1-2604920/b000052` |
| Ericsson | R1-2603673<br>R1-2605343<br>R1-2606780 | RAN1 #125<br>RAN1 #126 | PROPOSAL | Ericsson의 각 Proposal은 해당 TDoc의 Table 1을 RAN1 CB-BSR 시뮬레이션 파라미터의 출발점으로 사용하고, LS를 통해 RAN2와 그 파라미터를 확인하는 방안을 제안했다. | [C022](#ap-c022) `R1-2603673/b000039`<br>[C023](#ap-c023) `R1-2603673/b000039`<br>[C104](#ap-c104) `R1-2605343/b000047`<br>[C105](#ap-c105) `R1-2605343/b000047`<br>[C121](#ap-c121) `R1-2606780/b000048`<br>[C122](#ap-c122) `R1-2606780/b000048` |

#### 해석 메모

C080은 연구자가 승인한 [0,171)만 사용한다. 뒤의 “, including”이나 defer된 목록 fragment를 덧붙이지 않는다. 각 TDoc의 Table 1은 서로 별도의 원문 표이며, 이 보고서는 승인 span에 없는 표의 수치나 조건을 새 주장으로 옮기지 않는다.

#### 원문 확인

아래는 이 절에 사용한 승인 span의 원문이다. 문자열이 정확히 같은 승인 span은 한 번 인용하고 모든 TDoc·승인 번호를 함께 표시했다. 전체 ID·member·EvidenceRef는 [5절의 proposition별 provenance](#proposition-provenance)에서 확인할 수 있다.

[C039](#ap-c039) — R1-2604147:

```text
RAN1 to discuss and define detailed evaluation assumptions for DM-RS identification and payload decoding.
```

[C080](#ap-c080) — R1-2604920:

```text
The assumptions on the time domain allocation for CB-PUSCH within a slot should be discussed first considering the progress for general PUSCH study in agenda item 10.5.2.3
```

[C086](#ap-c086) — R1-2604920:

```text
RAN1 needs to discuss the modelling of channel correlation for UL MU-MIMO using CB-PUSCH.
```

[C087](#ap-c087) — R1-2604920:

```text
In addition to DMRS design, other solutions such as UE dedicated preambles are still under discussion in RAN1 to reduce/mitigate the potential collisions in shared/non-orthogonal resources.
```

[C022](#ap-c022) — R1-2603673:

```text
Proposal 2Use Table 1 as a starting point for CB-BSR simulation parameters in RAN1.
```

[C023](#ap-c023), [C105](#ap-c105), [C122](#ap-c122) — R1-2603673, R1-2605343, R1-2606780:

```text
Confirm the parameters with RAN2 in an LS.
```

[C104](#ap-c104), [C121](#ap-c121) — R1-2605343, R1-2606780:

```text
Proposal 3Use Table 1 as a starting point for CB-BSR simulation parameters in RAN1.
```

원문 문서: R1-2603673: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603673/R1-2603673.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603673/document.jsonl.gz>); R1-2604147: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604147/R1-2604147.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604147/document.jsonl.gz>); R1-2604920: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604920/R1-2604920.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604920/document.jsonl.gz>); R1-2605343: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2605343/R1-2605343.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2605343/document.jsonl.gz>); R1-2606780: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2606780/R1-2606780.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2606780/document.jsonl.gz>)

<a id="item-8"></a>

### 3.8 추가 연구의 범위와 RAN2 회신 시점

#### 기술 질문

Contributions는 추가 연구 대상과 RAN2에 전달할 범위·회신 시점을 어떻게 서술하는가?

#### 회사별 Contribution

| 회사/조직 | TDoc | Meeting | Kind | 한글 요약 | EvidenceRef |
|---|---|---|---|---|---|
| vivo | R1-2603620 | RAN1 #125 | OBSERVATION | vivo의 해당 Observation은 RAN2가 언급한 방법을 포함한 UE 측 uplink resource request 후보 메커니즘을 RAN1이 이미 추가 연구 대상으로 합의했다고 서술했다. 이 보고서는 이를 contribution의 관찰 문구로만 인용한다. | [C001](#ap-c001) `R1-2603620/b000014` |
| vivo | R1-2603620 | RAN1 #125 | PROPOSAL | vivo의 해당 Proposal은 RAN2가 언급한 방법을 포함하여 추가 연구 대상으로 합의되었다고 서술한 UE 측 자원 요청 후보를 RAN2에 알리고, 평가 가정과 잠재적 규격 영향을 포함해 후보 연구를 계속하겠다고 전달하는 방안을 제안했다. | [C003](#ap-c003) `R1-2603620/b000033`<br>[C004](#ap-c004) `R1-2603620/b000034` |
| Huawei, HiSilicon | R1-2604920 | RAN1 #125 | CONCLUSION | Huawei/HiSilicon의 해당 contribution의 conclusion에서는 관련 PUSCH·DMRS 사항과 가정 및 평가 관찰이 합의될 때까지, 충돌 시 UE 구분과 각 payload 복호 확률에 관한 견해를 담은 RAN2 회신 LS를 미루는 내용을 제시했다. | [C088](#ap-c088) `R1-2604920/b000053` |

#### 해석 메모

C001의 “RAN1 already agreed”는 vivo contribution 작성자의 서술이다. 독립적인 회의 권위 근거로 검증한 합의가 아니다. C003·C004는 전달·추가 연구를 제안하는 contribution이고, C088도 contribution conclusion이다. 어느 것도 이 보고서에서 채택이나 meeting agreement로 승격하지 않는다.

#### 원문 확인

아래는 이 절에 사용한 승인 span의 원문이다. 문자열이 정확히 같은 승인 span은 한 번 인용하고 모든 TDoc·승인 번호를 함께 표시했다. 전체 ID·member·EvidenceRef는 [5절의 proposition별 provenance](#proposition-provenance)에서 확인할 수 있다.

[C001](#ap-c001) — R1-2603620:

```text
Observation 1: RAN1 already agreed the candidate mechanisms for further study for UE-side uplink resource request, including the method mentioned by RAN2.
```

[C003](#ap-c003) — R1-2603620:

```text
Proposal 1: RAN1 informs RAN2 of the candidate mechanisms agreed for further study in RAN1 for UE-side uplink resource request, including the method mentioned by RAN2.
```

[C004](#ap-c004) — R1-2603620:

```text
Proposal 2: RAN1 informs RAN2 that it will continue studying these candidate mechanisms, including the evaluation assumptions and potential specification impact.
```

[C088](#ap-c088) — R1-2604920:

```text
RAN1 to postpone the reply LS to RAN2 with their view on probability of differentiating the UEs and decoding of their respective payload when there is a collision until both the relevant aspects/assumptions of PUSCH and DMRS and the observation from the evaluation are agreed.
```

원문 문서: R1-2603620: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603620/R1-2603620.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603620/document.jsonl.gz>); R1-2604920: [raw ZIP](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604920/R1-2604920.zip>) / [normalized](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604920/document.jsonl.gz>)

## 4. 회사별 빠른 인덱스

이 인덱스는 제출자 메타데이터별 탐색을 돕는다. 회사의 전체 입장이나 지지 범위를 뜻하지 않는다.

| 회사/조직 | 승인 근거가 있는 TDoc | Technical items | AcceptedProposition 별칭 |
|---|---|---|---|
| Ericsson | R1-2603673, R1-2605343, R1-2606780 | [3.1](#item-1), [3.2](#item-2), [3.3](#item-3), [3.4](#item-4), [3.5](#item-5), [3.7](#item-7) | [C012](#ap-c012), [C013](#ap-c013), [C014](#ap-c014), [C015](#ap-c015), [C016](#ap-c016), [C017](#ap-c017), [C018](#ap-c018), [C019](#ap-c019), [C020](#ap-c020), [C021](#ap-c021), [C022](#ap-c022), [C023](#ap-c023), [C090](#ap-c090), [C091](#ap-c091), [C092](#ap-c092), [C093](#ap-c093), [C094](#ap-c094), [C095](#ap-c095), [C096](#ap-c096), [C097](#ap-c097), [C098](#ap-c098), [C099](#ap-c099), [C100](#ap-c100), [C101](#ap-c101), [C102](#ap-c102), [C103](#ap-c103), [C104](#ap-c104), [C105](#ap-c105), [C107](#ap-c107), [C108](#ap-c108), [C109](#ap-c109), [C110](#ap-c110), [C111](#ap-c111), [C112](#ap-c112), [C113](#ap-c113), [C114](#ap-c114), [C115](#ap-c115), [C116](#ap-c116), [C117](#ap-c117), [C118](#ap-c118), [C119](#ap-c119), [C120](#ap-c120), [C121](#ap-c121), [C122](#ap-c122) |
| HiSilicon | R1-2604920 | [3.1](#item-1), [3.4](#item-4), [3.7](#item-7), [3.8](#item-8) | [C080](#ap-c080), [C084](#ap-c084), [C085](#ap-c085), [C086](#ap-c086), [C087](#ap-c087), [C088](#ap-c088) |
| Huawei | R1-2604920 | [3.1](#item-1), [3.4](#item-4), [3.7](#item-7), [3.8](#item-8) | [C080](#ap-c080), [C084](#ap-c084), [C085](#ap-c085), [C086](#ap-c086), [C087](#ap-c087), [C088](#ap-c088) |
| Ofinno | R1-2604209 | [3.2](#item-2) | [C067](#ap-c067), [C068](#ap-c068), [C069](#ap-c069), [C070](#ap-c070) |
| OPPO | R1-2604097 | [3.1](#item-1), [3.3](#item-3) | [C026](#ap-c026), [C027](#ap-c027), [C028](#ap-c028) |
| Samsung | R1-2604147 | [3.1](#item-1), [3.4](#item-4), [3.6](#item-6), [3.7](#item-7) | [C037](#ap-c037), [C039](#ap-c039), [C041](#ap-c041), [C042](#ap-c042), [C044](#ap-c044), [C046](#ap-c046), [C048](#ap-c048), [C050](#ap-c050) |
| vivo | R1-2603620 | [3.1](#item-1), [3.8](#item-8) | [C001](#ap-c001), [C002](#ap-c002), [C003](#ap-c003), [C004](#ap-c004), [C005](#ap-c005) |

NEC의 R1-2603806에는 추출된 SemanticEvidence가 있지만 두 candidate가 연구자 결정으로 제외되어 이 기술 주장 인덱스에 포함하지 않았다. 나머지 미포함 TDoc의 inspection·추출·승인 상태도 아래에 남긴다. 미포함은 회사의 기술 제안 부재를 의미하지 않는다.

## 5. 원문 파일 인덱스

1. **Raw DOCX/member → 원 contribution 읽기.** 아래 raw ZIP을 열어 표시된 member를 읽는다. Member 이름은 실제 archive entry이며 별도로 추출된 로컬 파일 경로를 꾸며 쓰지 않았다.
2. **Normalized document + EvidenceRef → 정확한 block 확인.** Block ID와 member를 함께 사용한다.
3. **SemanticEvidence → extractor 출력 확인.** EvidenceKind와 contribution scope를 확인한다.
4. **AcceptedProposition → 연구자 승인 보고·비교 단위 확인.** 승인 ID와 source span으로 원문 범위를 확인한다.

| TDoc | 조직 | Meeting | Inspected | Raw ZIP | Member | Normalized artifact | SemanticEvidence artifact | 사용한 주요 EvidenceRef block |
|---|---|---|---|---|---|---|---|---|
| R1-2603495 | RAN2, OPPO | RAN1 #125 | Yes | [R1-2603495.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603495/R1-2603495.zip>) | R1-2603495(R2-2602815).docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603495/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/125/R1-2603495/evidence.jsonl.gz>) | 사용한 승인 근거 없음 |
| R1-2603620 | vivo | RAN1 #125 | Yes | [R1-2603620.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603620/R1-2603620.zip>) | R1-2603620_Discussion on contention based PUSCH transmission.docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603620/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/125/R1-2603620/evidence.jsonl.gz>) | `b000014`, `b000029`, `b000033`, `b000034`, `b000035` |
| R1-2603671 | Spreadtrum, UNISOC | RAN1 #125 | Yes | [R1-2603671.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603671/R1-2603671.zip>) | R1-2603671.docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603671/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/125/R1-2603671/evidence.jsonl.gz>) | 사용한 승인 근거 없음 |
| R1-2603673 | Ericsson | RAN1 #125 | Yes | [R1-2603673.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603673/R1-2603673.zip>) | R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603673/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/125/R1-2603673/evidence.jsonl.gz>) | `b000034`, `b000035`, `b000036`, `b000037`, `b000038`, `b000039` |
| R1-2603806 | NEC | RAN1 #125 | Yes | [R1-2603806.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603806/R1-2603806.zip>) | R1-2603806.docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603806/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/125/R1-2603806/evidence.jsonl.gz>) | 사용한 승인 근거 없음 |
| R1-2603807 | NEC | RAN1 #125 | Yes | [R1-2603807.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603807/R1-2603807.zip>) | R1-2603807.docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603807/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/125/R1-2603807/evidence.jsonl.gz>) | 사용한 승인 근거 없음 |
| R1-2603957 | Xiaomi | RAN1 #125 | Yes | [R1-2603957.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603957/R1-2603957.zip>) | R1-2603957.docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2603957/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/125/R1-2603957/evidence.jsonl.gz>) | 사용한 승인 근거 없음 |
| R1-2604082 | ZTE Corporation, Sanechips | RAN1 #125 | No | [R1-2604082.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604082/R1-2604082.zip>) | R1-2604082 [Draft] Reply LS on evaluation assumptions for contention based PUSCH transmission.doc | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604082/document.jsonl.gz>) | not locally resolved | 사용한 승인 근거 없음 |
| R1-2604097 | OPPO | RAN1 #125 | Yes | [R1-2604097.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604097/R1-2604097.zip>) | R1-2604097/; R1-2604097/R1-2604097 Discussion on LS on evaluation assumptions for contention based PUSCH transmission-v2.docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604097/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/125/R1-2604097/evidence.jsonl.gz>) | `b000016`, `b000038`, `b000039` |
| R1-2604147 | Samsung | RAN1 #125 | Yes | [R1-2604147.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604147/R1-2604147.zip>) | R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604147/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/125/R1-2604147/evidence.jsonl.gz>) | `b000022`, `b000024`, `b000026`, `b000033`, `b000034`, `b000043`, `b000047` |
| R1-2604209 | Ofinno | RAN1 #125 | Yes | [R1-2604209.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604209/R1-2604209.zip>) | R1-2604209 Discussion on Reply LS on evaluation assumptions for contention based PUSCH transmission.docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604209/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/125/R1-2604209/evidence.jsonl.gz>) | `b000015`, `b000022` |
| R1-2604529 | Fainity Innovation | RAN1 #125 | No | [R1-2604529.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604529/R1-2604529.zip>) | R1-2604529 - RAN1#125 10.5.5 - Fainity Innovation.docx; __MACOSX/._R1-2604529 - RAN1#125 10.5.5 - Fainity Innovation.docx | not locally resolved | not locally resolved | 사용한 승인 근거 없음 |
| R1-2604657 | Google | RAN1 #125 | No | [R1-2604657.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604657/R1-2604657.zip>) | R1-2604657 draft reply LS on evaluation for contention based CG-PUSCH.docx; __MACOSX/._R1-2604657 draft reply LS on evaluation for contention based CG-PUSCH.docx | not locally resolved | not locally resolved | 사용한 승인 근거 없음 |
| R1-2604920 | Huawei, HiSilicon | RAN1 #125 | Yes | [R1-2604920.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604920/R1-2604920.zip>) | R1-2604920.docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/125/R1-2604920/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/125/R1-2604920/evidence.jsonl.gz>) | `b000045`, `b000049`, `b000050`, `b000051`, `b000052`, `b000053` |
| R1-2605343 | Ericsson | RAN1 #126 | Yes | [R1-2605343.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2605343/R1-2605343.zip>) | R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2605343/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/126/R1-2605343/evidence.jsonl.gz>) | `b000040`, `b000041`, `b000042`, `b000043`, `b000044`, `b000045`, `b000046`, `b000047` |
| R1-2606317 | Fainity Innovation | RAN1 #126 | No | [R1-2606317.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2606317/R1-2606317.zip>) | R1-2606317 - RAN1#126 10.5.5 - Fainity Innovation.docx; __MACOSX/._R1-2606317 - RAN1#126 10.5.5 - Fainity Innovation.docx | not locally resolved | not locally resolved | 사용한 승인 근거 없음 |
| R1-2606713 | Huawei, HiSilicon | RAN1 #126 | Yes | [R1-2606713.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2606713/R1-2606713.zip>) | R1-2606713.docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2606713/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/126/R1-2606713/evidence.jsonl.gz>) | 사용한 승인 근거 없음 |
| R1-2606780 | Ericsson | RAN1 #126 | Yes | [R1-2606780.zip](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2606780/R1-2606780.zip>) | R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx | [document.jsonl.gz](</home/jjuns/3gpp-study-engine/data/normalized/documents/ran1/126/R1-2606780/document.jsonl.gz>) | [evidence.jsonl.gz](</home/jjuns/3gpp-study-engine/data/derived/evidence/ran1/126/R1-2606780/evidence.jsonl.gz>) | `b000041`, `b000042`, `b000043`, `b000044`, `b000045`, `b000046`, `b000047`, `b000048` |

R1-2604082의 normalized 파일은 존재하지만 receipt 상태는 `unsupported_format`이며 inspection은 완료되지 않았다. 파일 존재를 inspection 성공으로 세지 않았다. 나머지 세 실패 문서의 normalized artifact와 네 실패 문서의 SemanticEvidence artifact는 현재 locally resolved되지 않는다.

### 문서별 상태와 저장된 official URL

| TDoc | SemanticEvidence 수 | AcceptedPropositions used | Discussion | Stored official URL |
|---|---:|---|---|---|
| R1-2603495 | 0 | 0 | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603495.zip) |
| R1-2603620 | 10 | [C001](#ap-c001), [C002](#ap-c002), [C003](#ap-c003), [C004](#ap-c004), [C005](#ap-c005) | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603620.zip) |
| R1-2603671 | 0 | 0 | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603671.zip) |
| R1-2603673 | 7 | [C012](#ap-c012), [C013](#ap-c013), [C014](#ap-c014), [C015](#ap-c015), [C016](#ap-c016), [C017](#ap-c017), [C018](#ap-c018), [C019](#ap-c019), [C020](#ap-c020), [C021](#ap-c021), [C022](#ap-c022), [C023](#ap-c023) | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603673.zip) |
| R1-2603806 | 2 | 0 | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603806.zip) |
| R1-2603807 | 0 | 0 | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603807.zip) |
| R1-2603957 | 0 | 0 | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603957.zip) |
| R1-2604082 | 0 | 0 | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604082.zip) |
| R1-2604097 | 9 | [C026](#ap-c026), [C027](#ap-c027), [C028](#ap-c028) | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604097.zip) |
| R1-2604147 | 15 | [C037](#ap-c037), [C039](#ap-c039), [C041](#ap-c041), [C042](#ap-c042), [C044](#ap-c044), [C046](#ap-c046), [C048](#ap-c048), [C050](#ap-c050) | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604147.zip) |
| R1-2604209 | 7 | [C067](#ap-c067), [C068](#ap-c068), [C069](#ap-c069), [C070](#ap-c070) | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604209.zip) |
| R1-2604529 | 0 | 0 | 메타데이터 관련성만 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604529.zip) |
| R1-2604657 | 0 | 0 | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604657.zip) |
| R1-2604920 | 10 | [C080](#ap-c080), [C084](#ap-c084), [C085](#ap-c085), [C086](#ap-c086), [C087](#ap-c087), [C088](#ap-c088) | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604920.zip) |
| R1-2605343 | 9 | [C090](#ap-c090), [C091](#ap-c091), [C092](#ap-c092), [C093](#ap-c093), [C094](#ap-c094), [C095](#ap-c095), [C096](#ap-c096), [C097](#ap-c097), [C098](#ap-c098), [C099](#ap-c099), [C100](#ap-c100), [C101](#ap-c101), [C102](#ap-c102), [C103](#ap-c103), [C104](#ap-c104), [C105](#ap-c105) | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Docs/R1-2605343.zip) |
| R1-2606317 | 0 | 0 | 메타데이터 관련성만 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Docs/R1-2606317.zip) |
| R1-2606713 | 0 | 0 | 선택 Chair Note 참조 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Docs/R1-2606713.zip) |
| R1-2606780 | 9 | [C107](#ap-c107), [C108](#ap-c108), [C109](#ap-c109), [C110](#ap-c110), [C111](#ap-c111), [C112](#ap-c112), [C113](#ap-c113), [C114](#ap-c114), [C115](#ap-c115), [C116](#ap-c116), [C117](#ap-c117), [C118](#ap-c118), [C119](#ap-c119), [C120](#ap-c120), [C121](#ap-c121), [C122](#ap-c122) | 메타데이터 관련성만 확인 | [official ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Docs/R1-2606780.zip) |

Official URL은 기존 metadata에 저장된 값이다. 이 보고서 작성 중 접속하거나 다운로드하지 않았다. Chair Note 미확인은 미논의를 뜻하지 않으며, 위의 Discussion 정보는 기술 주장 근거가 아니다.

<a id="proposition-provenance"></a>

### Proposition별 승인 ID와 EvidenceRef

각 EvidenceRef의 char span은 SemanticEvidence의 원문 block 범위다. Accepted source span은 별도로 표시하며, SourceUnit 문자열 안의 `[start,end)` 범위다. 특히 C080의 승인 범위와 전체 SemanticEvidence 범위를 혼동하지 않는다.

<a id="ap-c001"></a>

#### C001 — R1-2603620 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-bc19576458444699ab8393a4c10649962d715e8f3eb5c6e9766010dbc61e4878`.
- Candidate ID: `proposition-candidate-5863f8f08f52ca5c21474011e5ae79f9cc54f0d42011fce1cf0c55c10e7cdd5f`.
- Review ID: `proposition-review-1f7e9c2e917b152e363d1f23daece9e0fa33dce7acfd71a5fe8ddbd0d773d903`.
- SourceUnit ID: `proposition-source-58892dd5f9e3e7e1a6a96fc418e68233f0504e3d942d874d1ba34118b8e9256d`.
- SemanticEvidence ID: `ev-f57cd929191b1ccfba67c704`.
- Organization metadata: vivo.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,154)`.
- Member: `R1-2603620_Discussion on contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603620",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603620_Discussion on contention based PUSCH transmission.docx",
      "block_id": "b000014",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 154,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c002"></a>

#### C002 — R1-2603620 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-4e41e73338845cbfdc7320ddb8dc471debcf0127b93a2e8c088bc7b42d73dc8b`.
- Candidate ID: `proposition-candidate-8475d06dce6ddbdea74be08a8151a62c97043fdefadb526dd30b624c3265ebf4`.
- Review ID: `proposition-review-f428fa50014be8f899b561ec7d1341eb57b49238a063a00db985eeed1a40ec6e`.
- SourceUnit ID: `proposition-source-2601b252dbc4f9ced6ea31fb4afa66193b2ece08ff16d2b35f8c5234b8169af5`.
- SemanticEvidence ID: `ev-883a96c65a382b5493a16bc4`.
- Organization metadata: vivo.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,242)`.
- Member: `R1-2603620_Discussion on contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603620",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603620_Discussion on contention based PUSCH transmission.docx",
      "block_id": "b000029",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 242,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c003"></a>

#### C003 — R1-2603620 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-46507f472fecafdd271b498c8a4b81d5683bc82a494f0ac66cfbfe89d3f4f4c2`.
- Candidate ID: `proposition-candidate-d50b34eca4c6855cb6e05baa0f14e105182dc1553cad2faf32a873477fcf338d`.
- Review ID: `proposition-review-d81f6328a5ba1044b619946e0e0c819a570fa7c55d686d305136d463e28c6a63`.
- SourceUnit ID: `proposition-source-ce9b5f7eb65ddb8470571fc6975178c9a8e26dafc6f928fcf03e49b583af60f6`.
- SemanticEvidence ID: `ev-b2dc8c663824f70687fef3a1`.
- Organization metadata: vivo.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,167)`.
- Member: `R1-2603620_Discussion on contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603620",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603620_Discussion on contention based PUSCH transmission.docx",
      "block_id": "b000033",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 167,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c004"></a>

#### C004 — R1-2603620 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-3cacc317ca661940104ed5147f8745d567cc1a327be97e1ce27e1a5f8a94ff84`.
- Candidate ID: `proposition-candidate-8956277660951ceabb41737b73f6694d8f0f65de2d4d8d5eaf86769959b39e5a`.
- Review ID: `proposition-review-a9d51f4495271b4d28635ef6a21616d821bdf4c2b08594a5918e5099e758b3fe`.
- SourceUnit ID: `proposition-source-5e0201a4680348514c769bef8951c30d9242bce53bd68a0e9ce9c40d69f753ea`.
- SemanticEvidence ID: `ev-43be6256cabcc7cadfb348d9`.
- Organization metadata: vivo.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,161)`.
- Member: `R1-2603620_Discussion on contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603620",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603620_Discussion on contention based PUSCH transmission.docx",
      "block_id": "b000034",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 161,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c005"></a>

#### C005 — R1-2603620 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-d60dc2d1c93e10f351a9c5bf5e1ac5263623356a26378cfebad39c4f8d25a961`.
- Candidate ID: `proposition-candidate-2f8130b5ccc21715b49717f85c33dcc126d09e8e64069df2addcc687f81f24e2`.
- Review ID: `proposition-review-a6972a2ac8a1e071724838ccbdebea8928c1ae18eede660222522779ea99b429`.
- SourceUnit ID: `proposition-source-46fbd0d5adec3f9a53d4af772f1ddf6eb7ceca36582ebeafd406269fd657bfa2`.
- SemanticEvidence ID: `ev-a0ef89b2babcdb2c8f5bc35a`.
- Organization metadata: vivo.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,178)`.
- Member: `R1-2603620_Discussion on contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603620",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603620_Discussion on contention based PUSCH transmission.docx",
      "block_id": "b000035",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 178,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c012"></a>

#### C012 — R1-2603673 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-3438f559de5b03dd8dd7b03e54c5439dd831a6e56c70fcfb8dbd69dea3da3116`.
- Candidate ID: `proposition-candidate-622e7f5b5527e189279cbb7288b53f16718cab6158a5da7a65f04fb90aee1a83`.
- Review ID: `proposition-review-04cc9824d40c0d8cdf826003f6d5929220e0a4fa51793661426d3b11120e38af`.
- SourceUnit ID: `proposition-source-2005eb96c1d954eb028c69ac3e25be5d71fc62e48ba52051a1a7d1d98db98ac2`.
- SemanticEvidence ID: `ev-47f0a35550272f6cdc304012`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,153)`.
- Member: `R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603673",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000034",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 312,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c013"></a>

#### C013 — R1-2603673 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-8f8b2aa6fe05af29da89d3415d2f4d911bfb216b2e05cf0826231ebe04b7b3dc`.
- Candidate ID: `proposition-candidate-9a7b3f132b7c1085fb69b4373e0d110d020e6f89355bb5ef0d13dd5d73dc67c8`.
- Review ID: `proposition-review-5ec06e088ee7631e96d4b3e0dfa63065a3f4ac9b53db3512113e94d5fa915f32`.
- SourceUnit ID: `proposition-source-2005eb96c1d954eb028c69ac3e25be5d71fc62e48ba52051a1a7d1d98db98ac2`.
- SemanticEvidence ID: `ev-47f0a35550272f6cdc304012`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[155,312)`.
- Member: `R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603673",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000034",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 312,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c014"></a>

#### C014 — R1-2603673 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-bf3cdbc16f4a673db8022871b02f8d2596667aa4417bb1d4e7939bf59a30d6da`.
- Candidate ID: `proposition-candidate-f91b72d01d0fae48605c058610a070316f005f7ed7b17bf28508ad96fd7f1f76`.
- Review ID: `proposition-review-cdf9ea69d88571367f2a2e63a6d41ac949fa16a455f0cb58af774f0e0a09c07d`.
- SourceUnit ID: `proposition-source-3f680905be353baf2b69f5652e79925ba9a34274b223db5f9de083e7717b13ab`.
- SemanticEvidence ID: `ev-70e0db8a295fc3f111cf27cc`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,255)`.
- Member: `R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603673",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000035",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 255,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c015"></a>

#### C015 — R1-2603673 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-09350ec304ea4bfda4463a83db9fd10cf57b6414dfcd41155ba8b91a73549995`.
- Candidate ID: `proposition-candidate-e8991998272428ebfe09fb4962c583f1b7d01bdf32a9e85486077343a3042010`.
- Review ID: `proposition-review-4d702c284225db06c0494d84d8afbbd34af8bc2fd81cd61bb4f8ffc080b45614`.
- SourceUnit ID: `proposition-source-77c5fa459e4ea266707cb1e2c56153bafeb8a13ea1d2c67e207f8e59311d426a`.
- SemanticEvidence ID: `ev-b13be120b437dd566f662b5b`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,153)`.
- Member: `R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603673",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000036",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 153,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c016"></a>

#### C016 — R1-2603673 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-2e3054bdbc15e36abea85922c448457f235d5f92b772f36be296a55e76809900`.
- Candidate ID: `proposition-candidate-4eeabe8eab186a07292b659930af2c5460cf06d69b77d521f636d1d7e96835c3`.
- Review ID: `proposition-review-906f622df7de228835530d0e1a787877ff3e8ef0dba9e4789f3c8a81823f6917`.
- SourceUnit ID: `proposition-source-6ffbf28b00b147a777575a79b51f5e2b8df4f8579fa5360f02414c2ed7534644`.
- SemanticEvidence ID: `ev-1f24d115c7f4d91cdee5eb85`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,214)`.
- Member: `R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603673",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000037",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 430,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c017"></a>

#### C017 — R1-2603673 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-67234715514c0ad90e02d15f0238d4ad1fd8e19af6e9e0cc661fc6aa15b364f6`.
- Candidate ID: `proposition-candidate-9eb21b4f57ade6a887dd3569ed68547f6166c2ecfd8fb5043afc758094da3e92`.
- Review ID: `proposition-review-d1cc401ec59a6924fd4d962e3a1e114d97bc84f6bba7729cb6eaadd4f012a103`.
- SourceUnit ID: `proposition-source-6ffbf28b00b147a777575a79b51f5e2b8df4f8579fa5360f02414c2ed7534644`.
- SemanticEvidence ID: `ev-1f24d115c7f4d91cdee5eb85`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[216,430)`.
- Member: `R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603673",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000037",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 430,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c018"></a>

#### C018 — R1-2603673 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-1f9c27c5d82a07c9ddb72104adccf4b9c6c8fece03b3a3bd38adf748ecb70713`.
- Candidate ID: `proposition-candidate-4347c35bd9c872c2c2f926e7d7ceb20d80516740075b2c1ea9f1fb92a8268357`.
- Review ID: `proposition-review-9878309a5dcbcc30e2a4ca00a130cbef0474148ae4430557582b4d32314d1598`.
- SourceUnit ID: `proposition-source-1249aa7af3ba87c24e41dd29a8c38d07444da73c775eddf1415149e202a6001e`.
- SemanticEvidence ID: `ev-ab6c5bc6a6c22937eaaa7f41`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,219)`.
- Member: `R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603673",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000038",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 664,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c019"></a>

#### C019 — R1-2603673 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-a6f7ed99bab4d93b36a332a0e0c0a8127a80212d9c47d59d41649e784981a6e0`.
- Candidate ID: `proposition-candidate-1a7ce199cce6d026c158f8dd50a3a3fc7335cd2e918b7f22992fbc8391a9c1e7`.
- Review ID: `proposition-review-c376034fde44c874288547ef3584aae84685bc02cc747051a58e9c98f2d5b611`.
- SourceUnit ID: `proposition-source-1249aa7af3ba87c24e41dd29a8c38d07444da73c775eddf1415149e202a6001e`.
- SemanticEvidence ID: `ev-ab6c5bc6a6c22937eaaa7f41`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[220,361)`.
- Member: `R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603673",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000038",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 664,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c020"></a>

#### C020 — R1-2603673 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-0de80444269cba9ae56c326d1482a9029ac71bcd6e28ef697281834859122857`.
- Candidate ID: `proposition-candidate-2e87a153118cf3d0f745de4bb715894394298d267df57ef0e11790a548b5ae23`.
- Review ID: `proposition-review-d1a0ada153bce7886eed69235f75b05f177ea69406c13b80a23e0798b88d0a7c`.
- SourceUnit ID: `proposition-source-1249aa7af3ba87c24e41dd29a8c38d07444da73c775eddf1415149e202a6001e`.
- SemanticEvidence ID: `ev-ab6c5bc6a6c22937eaaa7f41`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[363,525)`.
- Member: `R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603673",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000038",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 664,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c021"></a>

#### C021 — R1-2603673 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-8f8b07903895b711d10b4dfec43ce6cd64b7a2c7e0c88d18ea8f01bddffb2221`.
- Candidate ID: `proposition-candidate-52696f89151c2b926fd6c7145e5b3f56497f2e161c0e37a46832a4fb2784e15c`.
- Review ID: `proposition-review-78a001ff8e511e9ba9264dc503e19d2f4548c985e5b438a8219314aa591941af`.
- SourceUnit ID: `proposition-source-1249aa7af3ba87c24e41dd29a8c38d07444da73c775eddf1415149e202a6001e`.
- SemanticEvidence ID: `ev-ab6c5bc6a6c22937eaaa7f41`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[527,664)`.
- Member: `R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603673",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000038",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 664,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c022"></a>

#### C022 — R1-2603673 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-3874141474b8a5ed4faf692bf5c9170ed9ba581eac5bb2b9cd145afec60a3f06`.
- Candidate ID: `proposition-candidate-a5b44f3577c65e8f6797887f2ae78a11055f559bf7938320d76022e51ae70000`.
- Review ID: `proposition-review-3a4103cebb3196246a41329650734caa4c84bf527fc5c5ce51c71dd1736ba215`.
- SourceUnit ID: `proposition-source-90608c91526d0c781a3b75a64fcbf44eba3fb886cd0bcda9624b65dc95166aa5`.
- SemanticEvidence ID: `ev-b226630ad427f232f0515515`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,83)`.
- Member: `R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603673",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000039",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 127,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c023"></a>

#### C023 — R1-2603673 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-96fef0e234d4fd4f7db8106be6aafbbc6a198b51fec780fb42961806474346c9`.
- Candidate ID: `proposition-candidate-2a13b681ca40e8c90b6bad297ae243ea9629af0e551860ec01c584be7c9fd9cf`.
- Review ID: `proposition-review-8fb494679d5747349000b3dba3940cd91a57232f9d82cb67eedeef9037fa555e`.
- SourceUnit ID: `proposition-source-90608c91526d0c781a3b75a64fcbf44eba3fb886cd0bcda9624b65dc95166aa5`.
- SemanticEvidence ID: `ev-b226630ad427f232f0515515`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[85,127)`.
- Member: `R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2603673",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000039",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 127,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c026"></a>

#### C026 — R1-2604097 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-f09965568f7f38287c0eb4618a7dbe3b5834c8f96cfe89efdce176f645cc2e38`.
- Candidate ID: `proposition-candidate-d646518b87bd6d1429c75e5bf3e9682d11c04533c6aceea6947bdb5b990b5b5f`.
- Review ID: `proposition-review-1ead4bb5b1987b87ffc1069f161d5d3fa51d031d06d0e7690e134121f949a740`.
- SourceUnit ID: `proposition-source-cf630a91461da717d01c0a506a8e1268e4358cf924a10ac87c5fa2467d069bfb`.
- SemanticEvidence ID: `ev-15b6c5f5a0f50ec59947c0d3`.
- Organization metadata: OPPO.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,260)`.
- Member: `R1-2604097/R1-2604097 Discussion on LS on evaluation assumptions for contention based PUSCH transmission-v2.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604097",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604097/R1-2604097 Discussion on LS on evaluation assumptions for contention based PUSCH transmission-v2.docx",
      "block_id": "b000016",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 260,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c027"></a>

#### C027 — R1-2604097 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-05cd6ce388425f092cb3a7397786ff993c5df5c18473a747414c17acf6cab09a`.
- Candidate ID: `proposition-candidate-8dbb66d53b87b9b821e634508cb0585500b2c4c7d9670abb3a44833e35b2ff8e`.
- Review ID: `proposition-review-22cd2c84f53c72fedca1bdc9b78e5a96a11bcf700b718967c205f8d5f0877f80`.
- SourceUnit ID: `proposition-source-aa550860218acee5f20757f7772f3471133ce0f1574a4b5f462f5ff31cc2f116`.
- SemanticEvidence ID: `ev-8e10efd8f7b463551eca51a7`.
- Organization metadata: OPPO.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,174)`.
- Member: `R1-2604097/R1-2604097 Discussion on LS on evaluation assumptions for contention based PUSCH transmission-v2.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604097",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604097/R1-2604097 Discussion on LS on evaluation assumptions for contention based PUSCH transmission-v2.docx",
      "block_id": "b000038",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 174,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c028"></a>

#### C028 — R1-2604097 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-00f9bc705b27cbba011ec1f03bcde681f25821ad5137c061a119254308ce8365`.
- Candidate ID: `proposition-candidate-8c1a2c5f58d57eef33a792347b4fab7e991e856647259093dfd21d793df9eff4`.
- Review ID: `proposition-review-132d8dcafb437b8e2995b2cb9538cb912809054fb58ba0f3fd820e0fef6f1362`.
- SourceUnit ID: `proposition-source-737bb57789b121f0248b7cd021e72cce9d7d577bf8bce91cc34ddc31d154f187`.
- SemanticEvidence ID: `ev-968af71f0d935435fad2e93e`.
- Organization metadata: OPPO.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,286)`.
- Member: `R1-2604097/R1-2604097 Discussion on LS on evaluation assumptions for contention based PUSCH transmission-v2.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604097",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604097/R1-2604097 Discussion on LS on evaluation assumptions for contention based PUSCH transmission-v2.docx",
      "block_id": "b000039",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 286,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c037"></a>

#### C037 — R1-2604147 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-d333bf7b8a7d5879cf36624fc210e34653a97a45b959cf2ce49d498526eff36f`.
- Candidate ID: `proposition-candidate-6ff0c7a2aa0fe3f2cf75bcc0110ef0b5a9780dd904ad43f935ec5f09fa225c6b`.
- Review ID: `proposition-review-2e2605c053d2d028df46f700eb7282265a6675268480c681cfaa348ca7ff9ed0`.
- SourceUnit ID: `proposition-source-10ca580524768d9e490798ff72f97cf2025f2c61cd2d08b627ed1e01775891d9`.
- SemanticEvidence ID: `ev-2b71ee5264ad913389783950`.
- Organization metadata: Samsung.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[15,112)`.
- Member: `R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604147",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000022",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 112,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c039"></a>

#### C039 — R1-2604147 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-4d6b33d76f119515b5c92b61b8fda6b88c060d2d2f8a112ef7dc315504d92521`.
- Candidate ID: `proposition-candidate-f25b260b233020541497f56f9ab8b5c637ad350c6248df285fef25fa0f4dd360`.
- Review ID: `proposition-review-13246fcc9b48c275f126082dcdbe68ea4fdb9f74e12d400e6049069dfcedc550`.
- SourceUnit ID: `proposition-source-ee7b1349852ddbe9da83d11da7c767b1dbd37cc1e477d6f9de7a17b908ecb0fb`.
- SemanticEvidence ID: `ev-94bebe3b7564a29bc65afe36`.
- Organization metadata: Samsung.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[12,117)`.
- Member: `R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604147",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000024",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 117,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c041"></a>

#### C041 — R1-2604147 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-c603cede4db4c0d81ede1b2cdc2d1b3f184d17b108a3f0e77ea8dc6274e3393a`.
- Candidate ID: `proposition-candidate-55b84d7cfe0327c86f619e7cd53b9431a4cd52bf883b6dae57acf8a01c2b695c`.
- Review ID: `proposition-review-8fde1f3f9b21e154323cd3f79eac5652f429c68ce0ebd11c2d0f6e8fc3c59e4c`.
- SourceUnit ID: `proposition-source-c9dd561a7d38c3973040cd7b710869869fb64f685888edf5f0f40c39468776f8`.
- SemanticEvidence ID: `ev-928a166f868f8dbdca3ee796`.
- Organization metadata: Samsung.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[15,97)`.
- Member: `R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604147",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000026",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 293,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c042"></a>

#### C042 — R1-2604147 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-fd13f4c3c6f1a987421b650dc94fd8bad780166dd49713def79a36ceaab407a4`.
- Candidate ID: `proposition-candidate-68426d3deb73dd0fafe8dd3d03c1e0d2ed6940795c0b88bff2c7789729922541`.
- Review ID: `proposition-review-894c6df70c3aa758c2dcbe07dd82121d7a30876a40434f57485de1a218b71bb2`.
- SourceUnit ID: `proposition-source-c9dd561a7d38c3973040cd7b710869869fb64f685888edf5f0f40c39468776f8`.
- SemanticEvidence ID: `ev-928a166f868f8dbdca3ee796`.
- Organization metadata: Samsung.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[98,293)`.
- Member: `R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604147",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000026",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 293,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c044"></a>

#### C044 — R1-2604147 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-df901dd8bc5ea26c461eaab79b1b3f247dd6ad8ef9a07adda9c8c9eb650a7dbb`.
- Candidate ID: `proposition-candidate-bfebe69f14a1107e744ec32da47254495ae31e14e336d59a9aff441a5f030769`.
- Review ID: `proposition-review-4abdd751a598341cd439069e74695622c8a80f6bf73bdb4995a4126c58b08002`.
- SourceUnit ID: `proposition-source-19985a05d6a7967d16d5b1b2b8c97eb495ec9ba11b66da08b16467b6a5841582`.
- SemanticEvidence ID: `ev-e8694612d9f9ac92d00bb493`.
- Organization metadata: Samsung.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[15,232)`.
- Member: `R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604147",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000033",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 232,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c046"></a>

#### C046 — R1-2604147 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-0b66b95e48d96273faaa0b21ca8af6423d20decc23b72da6bc0dc261621f85c0`.
- Candidate ID: `proposition-candidate-b1949121b11bd3c674d11a5d18960c4737be394bcb11bb3bd67af5ca145f5172`.
- Review ID: `proposition-review-5e2764cb7cb9d04c341561e644a7523492c167712bebc0ae7a89263621ef5d4a`.
- SourceUnit ID: `proposition-source-2544d11f3fc59eea2c6756360ef27b19ffba3f9befeaeb310848aad00b71adf0`.
- SemanticEvidence ID: `ev-bf067597bdf2c54a90c2fa24`.
- Organization metadata: Samsung.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[15,130)`.
- Member: `R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604147",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000034",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 130,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c048"></a>

#### C048 — R1-2604147 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-2226f5097f8b7dc12d352c32cf5c8cbd2dea00e1781fff948ba1acb201f90697`.
- Candidate ID: `proposition-candidate-5a530e42ed6d88cec913ae0d1cd692a33b9707a505433f6ef21c76bd5960c30a`.
- Review ID: `proposition-review-f66d478f1756f37c9744aec24a4237b7656021a872ee4a1d530ce304bd8d64ed`.
- SourceUnit ID: `proposition-source-78613dce19e7b11ea7bbdd6a96a0deaa74013401f9c03c87cc55bcd4ac8f028c`.
- SemanticEvidence ID: `ev-c11414dac00e93550f85f568`.
- Organization metadata: Samsung.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[15,337)`.
- Member: `R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604147",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000043",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 337,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c050"></a>

#### C050 — R1-2604147 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-37166b354468856d67b91194a5b90111e7b3ee56a28e64cabaa2e3b314407f86`.
- Candidate ID: `proposition-candidate-606001e0f2ee1d6b159952cfec750b4c9ce260d74cf70ff3ab4088055708153b`.
- Review ID: `proposition-review-4f8d642ff703fe2cde5420af006e4f8c4d705fdc1ee8a3e007b1f1898a22c8d0`.
- SourceUnit ID: `proposition-source-fe8892b488ae32b8e08833a41388fd3d2e2da96bcc2147db7e4f5bdd7525ae9f`.
- SemanticEvidence ID: `ev-0d81bd9524c7c6d8e9de8fca`.
- Organization metadata: Samsung.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[15,345)`.
- Member: `R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604147",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000047",
      "block_type": "paragraph",
      "heading_path": [],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 345,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c067"></a>

#### C067 — R1-2604209 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-def14c0f471f6dc2f4fc00c96aca0d9c4cfe16cd8e057cfa653a6db9dbd610f7`.
- Candidate ID: `proposition-candidate-8222e168cc5538fa909fe974ce048b9f5ab26e3caa159e90346360d85eb5a7e5`.
- Review ID: `proposition-review-9ded33a61716ccd72404f7f67b0c28e37e981af1ef666ecb84c1dbaf8cd1033a`.
- SourceUnit ID: `proposition-source-1274aa19bfced1000c0d3240c1133381c39da73b5bddb109bbd29e7ce3088ead`.
- SemanticEvidence ID: `ev-b640b88ad0cb97a057b86820`.
- Organization metadata: Ofinno.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,101)`.
- Member: `R1-2604209 Discussion on Reply LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604209",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604209 Discussion on Reply LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000015",
      "block_type": "paragraph",
      "heading_path": [
        "Discussion",
        "Question 1: UE differentiation upon collision"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 231,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c068"></a>

#### C068 — R1-2604209 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-0b4cef3c0902c6b584dc80b0bc7ada8e6ce0c08eca18c5308d6a3d6acb01c403`.
- Candidate ID: `proposition-candidate-6bd3f397d750c1e5f948c3c4881fe35fdc0d437926a8715b4489189bd1ca631d`.
- Review ID: `proposition-review-ddabf54808cbc30e31889e7c4ff973675c988b4b3260cac5285e760d596f7c5e`.
- SourceUnit ID: `proposition-source-1274aa19bfced1000c0d3240c1133381c39da73b5bddb109bbd29e7ce3088ead`.
- SemanticEvidence ID: `ev-b640b88ad0cb97a057b86820`.
- Organization metadata: Ofinno.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[102,231)`.
- Member: `R1-2604209 Discussion on Reply LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604209",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604209 Discussion on Reply LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000015",
      "block_type": "paragraph",
      "heading_path": [
        "Discussion",
        "Question 1: UE differentiation upon collision"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 231,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c069"></a>

#### C069 — R1-2604209 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-0e5860dbda00960516c4b734b92a8697674c8fac336a50713c71001c98516bc8`.
- Candidate ID: `proposition-candidate-a81d6c23d9317067ca504a960ad782d49f8bb0b35349c1825c31f26959236154`.
- Review ID: `proposition-review-a26529e7866e724de7d8fbef73854812d5a7b5541586ef1cc48b81abd78c0772`.
- SourceUnit ID: `proposition-source-b46614c7e9854a96af041e98d8da2d33034f04664bfbf521cf1441bc8153460d`.
- SemanticEvidence ID: `ev-310f042015d9e2ea83a2e261`.
- Organization metadata: Ofinno.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,228)`.
- Member: `R1-2604209 Discussion on Reply LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604209",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604209 Discussion on Reply LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000022",
      "block_type": "paragraph",
      "heading_path": [
        "Discussion",
        "Question 1: UE differentiation upon collision"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 462,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c070"></a>

#### C070 — R1-2604209 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-70df0bce8d7e0317abd2522b27ccb8baed8b9deb4942284b4e357cd1e90e3700`.
- Candidate ID: `proposition-candidate-411b5ca69ebf997249e9873a8e66443f021dbec82cf4c83c143d3892f32739f5`.
- Review ID: `proposition-review-845133d8ac5b3c49eea35b51d742ecf075c0eb457c8f4a70320b9c105957af75`.
- SourceUnit ID: `proposition-source-b46614c7e9854a96af041e98d8da2d33034f04664bfbf521cf1441bc8153460d`.
- SemanticEvidence ID: `ev-310f042015d9e2ea83a2e261`.
- Organization metadata: Ofinno.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[229,462)`.
- Member: `R1-2604209 Discussion on Reply LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604209",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604209 Discussion on Reply LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000022",
      "block_type": "paragraph",
      "heading_path": [
        "Discussion",
        "Question 1: UE differentiation upon collision"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 462,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c080"></a>

#### C080 — R1-2604920 / CONCLUSION

- AcceptedProposition ID: `accepted-proposition-bfb1ca90296552ddddaf8f6eee3dcd6f49f73ca8b0b81d7d4bf7cd7f1e5b2e31`.
- Candidate ID: `proposition-candidate-9cbafa6468159a92f3caa37b8825c0428faf4881aa4da0275501036313cccb3d`.
- Review ID: `proposition-review-7f2abaa06bc01a2c578e118a13cca95df635f5f3a1b10d94f3b6ac76d91ca62b`.
- SourceUnit ID: `proposition-source-1e4b3e85b0305dd375c7ed79597c3810014fb148d3958b5708244cbaa874c2d4`.
- SemanticEvidence ID: `ev-841cafcdb84090bf607c7d7f`.
- Organization metadata: Huawei, HiSilicon.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,171)`.
- Member: `R1-2604920.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604920",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604920.docx",
      "block_id": "b000045",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 182,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c084"></a>

#### C084 — R1-2604920 / CONCLUSION

- AcceptedProposition ID: `accepted-proposition-5667e7862a10a231762b39c39b0d49a08f35fe3e1e9f7eb14ddecc7e048eca63`.
- Candidate ID: `proposition-candidate-16151649a6311575b17d7f1183be87836405f5da87d7ef9ed9174168a6c0ce00`.
- Review ID: `proposition-review-06d967cd6ad5cb0f9580016e14c30fae7a426fb1591aa82ff28fc4825b8e2004`.
- SourceUnit ID: `proposition-source-c1978492da2b9270ea9f930e2d44811cd3ede451012cf3b1a07881e551d860a4`.
- SemanticEvidence ID: `ev-c7f989f93aced1dc9f235f0a`.
- Organization metadata: Huawei, HiSilicon.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,196)`.
- Member: `R1-2604920.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604920",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604920.docx",
      "block_id": "b000049",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 196,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c085"></a>

#### C085 — R1-2604920 / CONCLUSION

- AcceptedProposition ID: `accepted-proposition-176c935145cae063320a2407bd45be58f58e1c9813db2781316eb1be81a8e07f`.
- Candidate ID: `proposition-candidate-57e64adc9733a6942dbfc711572700a5b5f8644af15a635fe8e902fabf4d16ad`.
- Review ID: `proposition-review-3d657ba1a3c31571a199d79ebd45472f28d4a7b9968b98d8722c5047eb630257`.
- SourceUnit ID: `proposition-source-4a0263c72a531c9e52c93ea68cad3a249dfcd774fcc4715269efad0727d18665`.
- SemanticEvidence ID: `ev-c6a523e87d59977de1866388`.
- Organization metadata: Huawei, HiSilicon.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,139)`.
- Member: `R1-2604920.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604920",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604920.docx",
      "block_id": "b000050",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 139,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c086"></a>

#### C086 — R1-2604920 / CONCLUSION

- AcceptedProposition ID: `accepted-proposition-d859398914b6ce76aef0b4415442b601861909363efd5505b2e457ec44e4911f`.
- Candidate ID: `proposition-candidate-281b9b9506297fd5d5c324469003618fceff973a5e5def8b04b611357aba74a8`.
- Review ID: `proposition-review-766a5995989f3786f60e124f19e5f77d4a89642904170621680dbfff2f9b046f`.
- SourceUnit ID: `proposition-source-c2c68422c3e740386ba2e6b48d49bbd78e5ea0db456b3acf662c003cc75ea7a3`.
- SemanticEvidence ID: `ev-9e6cc85d17add84856fefa8d`.
- Organization metadata: Huawei, HiSilicon.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,89)`.
- Member: `R1-2604920.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604920",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604920.docx",
      "block_id": "b000051",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 89,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c087"></a>

#### C087 — R1-2604920 / CONCLUSION

- AcceptedProposition ID: `accepted-proposition-ab46388a3eca3333c7e09f099e9af62f18819c2c8145ab100555020e565ef0e7`.
- Candidate ID: `proposition-candidate-82fd1743eb8baa9efbd3dcedbd737c66276eb4f94c4e865cff4ce9cae92d6550`.
- Review ID: `proposition-review-60e3f13b3d3e644a396945394002fda4fc9a95fa787d55f59c612e3a9de05246`.
- SourceUnit ID: `proposition-source-a39b609f5141ee664ac7146f084970ecb512bacaf4ab244b71b7abf324de0641`.
- SemanticEvidence ID: `ev-2ea177debf713eb2b43176be`.
- Organization metadata: Huawei, HiSilicon.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,189)`.
- Member: `R1-2604920.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604920",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604920.docx",
      "block_id": "b000052",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 189,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c088"></a>

#### C088 — R1-2604920 / CONCLUSION

- AcceptedProposition ID: `accepted-proposition-a72d57210a4f8e491218603ca4b61fdfc48f327aecc10dcf20778072754b398e`.
- Candidate ID: `proposition-candidate-9e69740dd32e957772525cce56028ea5399ce1a8989a13567185d18fc221f99b`.
- Review ID: `proposition-review-07684263c3902f2db383476f6ec0a94e4426f7c39af9372d5980628fad5172f0`.
- SourceUnit ID: `proposition-source-cefaa8258675073eb1c76178a2cfdd8dbf9af43a0f9732b09ff7866ec1cb3bd7`.
- SemanticEvidence ID: `ev-37a6227118c8c261f50ae55f`.
- Organization metadata: Huawei, HiSilicon.
- Meeting: RAN1 #125; scope: `contribution`.
- Accepted source span: `[0,276)`.
- Member: `R1-2604920.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2604920",
      "working_group": "RAN1",
      "meeting": "125",
      "member": "R1-2604920.docx",
      "block_id": "b000053",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 276,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c090"></a>

#### C090 — R1-2605343 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-ffc3453e0130d6f9925de39482db752bb574e0dc9fe3a0c9d6b33a18e2088b31`.
- Candidate ID: `proposition-candidate-2e05efe8baa6eefc7fa2ba52d4a6d14aae04d3aedb0e949d92ca1370525ae510`.
- Review ID: `proposition-review-b92b43825e745e2f1723a5e6d59d1e7a4dc07361290f2c026cd7c420aae16748`.
- SourceUnit ID: `proposition-source-061d76d898ddfdaee5d24424ec4db7c80b17981ed16f0c5824168b3f16c5eb54`.
- SemanticEvidence ID: `ev-2a2b139a9dd35b28161b4586`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,153)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000040",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 312,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c091"></a>

#### C091 — R1-2605343 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-12402bc962792fc641456e79719ab0619587749ee74061e6c57dad42997b526b`.
- Candidate ID: `proposition-candidate-4a040b01c0c3f0e452ca33409881eee438e1f6da669a1b5a306af0d05bad7c23`.
- Review ID: `proposition-review-d54133b43b4ba74fed4b424abc43526d23cb066a7b9537140e3746946f683f0a`.
- SourceUnit ID: `proposition-source-061d76d898ddfdaee5d24424ec4db7c80b17981ed16f0c5824168b3f16c5eb54`.
- SemanticEvidence ID: `ev-2a2b139a9dd35b28161b4586`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[155,312)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000040",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 312,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c092"></a>

#### C092 — R1-2605343 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-f84baf6ed5a9d0ed5c3dbbe4462a239dfc28dcbd931d0d682acad2d89fdc2ae8`.
- Candidate ID: `proposition-candidate-a6a202e20a240ed52ae112fad56913a3ef008b154ccbae1f20d89db5cb241632`.
- Review ID: `proposition-review-5aa438d876c59a917ccb3d0d605f4ef9c53819e3542b9d4f14cc5444bd38df41`.
- SourceUnit ID: `proposition-source-82ac911885b60272ffaf73604f136e601ae979b994fe66e9870c0f50b7004103`.
- SemanticEvidence ID: `ev-b2a637004149df337d23912e`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,255)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000041",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 255,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c093"></a>

#### C093 — R1-2605343 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-77024ecfbaf0383ecaf1867cdee913988c14d2de513d47414a5a73da725b8c54`.
- Candidate ID: `proposition-candidate-9ef949d62e19fe2a88aeaebb01992f37868300079c1833e85c7b12843a842928`.
- Review ID: `proposition-review-14073743b99e96fba43e4edf7ed1475e88deff209bb2cb2e3ed92efaff1f4616`.
- SourceUnit ID: `proposition-source-c95ff2010fd9c261f5128a84c3ac188e09d5f8cf68b86f05c40002939a1290ef`.
- SemanticEvidence ID: `ev-8a739a0ca14054e45b0bb3e4`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,191)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000042",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 191,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c094"></a>

#### C094 — R1-2605343 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-7451f4c3f06e2f1ad452c2159f3d1fe164c9500cff092c4acf7949f27f9e53c3`.
- Candidate ID: `proposition-candidate-fa604fd2fdf87623844205cc0eb9f914320f04d5f30227661b1e027ad146d125`.
- Review ID: `proposition-review-0e39cdc1a4ab4ad6e20e0d5a8252366aac1d00349ce7a5f012b53dee9ad6bbb3`.
- SourceUnit ID: `proposition-source-a45b8a4b49871d0a0077b63a91f46cbf0f38c1772479363886e968f129a493a6`.
- SemanticEvidence ID: `ev-0152efc91d8df0e09f752278`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,231)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000043",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 447,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c095"></a>

#### C095 — R1-2605343 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-d8797ef2216744857f927af457b1cf8423c517a30bf7b6e61aa22bbb40c94eca`.
- Candidate ID: `proposition-candidate-a855f64ae308aa4332c2a35f8e1df1923e6a07d627815e14b9f2c05b95293042`.
- Review ID: `proposition-review-784f91604660e561af8053b91e75f9679b91860237fd6680d16de5c106cf193a`.
- SourceUnit ID: `proposition-source-a45b8a4b49871d0a0077b63a91f46cbf0f38c1772479363886e968f129a493a6`.
- SemanticEvidence ID: `ev-0152efc91d8df0e09f752278`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[233,447)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000043",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 447,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c096"></a>

#### C096 — R1-2605343 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-9f43ee782c8e6dab26f678d1e6c173f58e500ab8adc8b8934164d44fbbea3a3a`.
- Candidate ID: `proposition-candidate-7a334c84f4987eb0ced2808390315b36faa08dd87d2d879a195f35ced013df47`.
- Review ID: `proposition-review-2518d4fe7344c106cdf258f3fca164b46af40e5973600d432c01213ebaa9fcb1`.
- SourceUnit ID: `proposition-source-9d2c12bed7e2362cb198c443d66ed22b36ed53b341e7e8a6ff3a97dd6f4f43b1`.
- SemanticEvidence ID: `ev-286f057cd51321426e38036d`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,120)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000044",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 267,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c097"></a>

#### C097 — R1-2605343 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-5c369d60a8bb9a4705e6b246c25bcc7f66bc95b20346b2164d50c4d4c070f070`.
- Candidate ID: `proposition-candidate-fe685b18ae483d73f4a233ffeeda9ebeaa266179604218b5dd26ff35477187bd`.
- Review ID: `proposition-review-50ca34829d2134a60772c1f6bc55f63dd0a0d618e160c2283b7b2a4b6658dd11`.
- SourceUnit ID: `proposition-source-9d2c12bed7e2362cb198c443d66ed22b36ed53b341e7e8a6ff3a97dd6f4f43b1`.
- SemanticEvidence ID: `ev-286f057cd51321426e38036d`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[122,267)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000044",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 267,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c098"></a>

#### C098 — R1-2605343 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-dc574103f55dea0f50e1e7d315d6cdf5ed921ae2cd01e455d1e64f4a5448a964`.
- Candidate ID: `proposition-candidate-6369894b60517f7837a3290900b8d3cfdbb8a23989b6d100e91819c740d51cea`.
- Review ID: `proposition-review-d01c282ef29d695d1ee7a15591696bef8a33e27c2f12abf0bf19c8265d460b4a`.
- SourceUnit ID: `proposition-source-104a032e854490a58d10ab90bb818e862918e0b0bbca8080cf73fb532e75b7e7`.
- SemanticEvidence ID: `ev-35479e4e8b0576e769cdbff5`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,219)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000045",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 664,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c099"></a>

#### C099 — R1-2605343 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-75246efa5a28992fa157757d1b6521815cc4e0328a43b91dd01f88d97369f395`.
- Candidate ID: `proposition-candidate-bd1850b3653e83238bfa33854e84763243c4028ce2f332459a72b60934b7018c`.
- Review ID: `proposition-review-6568e4794b65a14073058da2bcd018a0f6d8e761d864d5f1a9f8fd56843f2f1a`.
- SourceUnit ID: `proposition-source-104a032e854490a58d10ab90bb818e862918e0b0bbca8080cf73fb532e75b7e7`.
- SemanticEvidence ID: `ev-35479e4e8b0576e769cdbff5`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[220,361)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000045",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 664,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c100"></a>

#### C100 — R1-2605343 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-60b2799caf9613e9a94c3b85b7f28f87210ff3105b520348b505480a289354d0`.
- Candidate ID: `proposition-candidate-0e498dfef90768094285fc82e0bfa7dc0261a4a23fbdda9f79033b55eb89fc19`.
- Review ID: `proposition-review-ea7a01117b1f8fa6b6e35ee2f7302c7c6fe185d0dd8ff560ad5b0f7701ad76e6`.
- SourceUnit ID: `proposition-source-104a032e854490a58d10ab90bb818e862918e0b0bbca8080cf73fb532e75b7e7`.
- SemanticEvidence ID: `ev-35479e4e8b0576e769cdbff5`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[363,525)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000045",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 664,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c101"></a>

#### C101 — R1-2605343 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-025efeb3385cc177eb44d620f9e68f22cd856217d5293ad1abc5224f4277b5ff`.
- Candidate ID: `proposition-candidate-51ab434861c92f17ebf5b06893ae101484463a9287996f1f95158c57c78f1e15`.
- Review ID: `proposition-review-9c3bb90b8900990fb87eb31f55b1a81cc41c73b5c8db387cb476a6ed8c77ca20`.
- SourceUnit ID: `proposition-source-104a032e854490a58d10ab90bb818e862918e0b0bbca8080cf73fb532e75b7e7`.
- SemanticEvidence ID: `ev-35479e4e8b0576e769cdbff5`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[527,664)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000045",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 664,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c102"></a>

#### C102 — R1-2605343 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-93aeba39486b2d4e8bebcfb5fc9ad43a41d301b4c3a94e2a218e0bf564a7a920`.
- Candidate ID: `proposition-candidate-b43a3dc9f2ebcef9eb36704b81c92a675034bf60cbce53823ec5484216b69656`.
- Review ID: `proposition-review-a07963b5b80d34901d8baefc71fcd0e66993088d818ebedfe2f359e3f423f04d`.
- SourceUnit ID: `proposition-source-74497cae75379d790fb059784e3b2cb255b22347dcf8bb8407038a249fb26e56`.
- SemanticEvidence ID: `ev-19ad8f19258852c9802335df`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,255)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000046",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 326,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c103"></a>

#### C103 — R1-2605343 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-56950776e7ec6b232a005660f7680db095484958d5634dac5f42065d6a5931a3`.
- Candidate ID: `proposition-candidate-14afe0fcd1581865a711ffd1acfd0df26e7750e7451f3f1debdd57e380ba65e9`.
- Review ID: `proposition-review-c6a9c5b8f7a1c0d80a0d320d7ee9a584e446342dab81547538b04d28ff405525`.
- SourceUnit ID: `proposition-source-74497cae75379d790fb059784e3b2cb255b22347dcf8bb8407038a249fb26e56`.
- SemanticEvidence ID: `ev-19ad8f19258852c9802335df`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[256,326)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000046",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 326,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c104"></a>

#### C104 — R1-2605343 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-e85cefc0fda6c0f23776ab1d86d82238827332bcbf840d939ad51314354a1a70`.
- Candidate ID: `proposition-candidate-dd555cc8529c0da9f297ab9e569c39eb4c9117fe926ffbc6ac8c71ecba076426`.
- Review ID: `proposition-review-a951f94e922ff2f167602caf619f883256e6e5f33f4660da42eba252b6790dc8`.
- SourceUnit ID: `proposition-source-dfc8ee2ab5cb377e118d991a73bead43cc4f372ed58e7c57060228b506304b02`.
- SemanticEvidence ID: `ev-eda5f528b144228bd6d0ac26`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,83)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000047",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 127,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c105"></a>

#### C105 — R1-2605343 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-3a5a1c919c1246eaf336814823d702f52190e478acd138667e354e729691c1ee`.
- Candidate ID: `proposition-candidate-87ef12b7d7213c1551d0882a2ff7085179475b3c1eaad5fb647afc2d7ea5fed8`.
- Review ID: `proposition-review-dc031b9b322fd0a9ede363d47d147831ec4ce262721bb788b532684d3763008b`.
- SourceUnit ID: `proposition-source-dfc8ee2ab5cb377e118d991a73bead43cc4f372ed58e7c57060228b506304b02`.
- SemanticEvidence ID: `ev-eda5f528b144228bd6d0ac26`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[85,127)`.
- Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2605343",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000047",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 127,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c107"></a>

#### C107 — R1-2606780 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-ba362a91abcbc3f5b865baee861c441f6f93560a7614cad2807d61b33554407d`.
- Candidate ID: `proposition-candidate-3500796f9d9ea561fe41bca63e58f16483fca329d20d3785b88530a50c9a0be6`.
- Review ID: `proposition-review-2804211d91ac0c945925412b308cf9601cdb4fcbe09689ced050a99c0b0603c2`.
- SourceUnit ID: `proposition-source-0acccc19443b3ccd2da5eaa6f2b736ebd9123d22f0279bae5318e8f840067967`.
- SemanticEvidence ID: `ev-4e8a85c986f042a5aaee1e9e`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,153)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000041",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 312,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c108"></a>

#### C108 — R1-2606780 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-48949187545a29583e6f87621d3ed01006c28cd5695e9d224ff9e23f5248c8c7`.
- Candidate ID: `proposition-candidate-8721d5d928d0c7ed6211ab67ba97994975597833b2d603399ebe90d98d0b39e4`.
- Review ID: `proposition-review-7cd1c7952f8efc54d6d0afed06cf0b932c596aa1416ba3b00c61b631fe8addce`.
- SourceUnit ID: `proposition-source-0acccc19443b3ccd2da5eaa6f2b736ebd9123d22f0279bae5318e8f840067967`.
- SemanticEvidence ID: `ev-4e8a85c986f042a5aaee1e9e`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[155,312)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000041",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 312,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c109"></a>

#### C109 — R1-2606780 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-087221319a3edb0deb8b66902cae044c21641c1f423535380d805bbc71ecf6e5`.
- Candidate ID: `proposition-candidate-5c781fbc3937624cae4478f0a9cd77a66f01e74efcd104b2d0669c16a3af39cf`.
- Review ID: `proposition-review-3bb1bf671e2b53675e369c41f0d50a0d3357e9d8bf63db9877d6534513383bc1`.
- SourceUnit ID: `proposition-source-867be6c2cc691509c525a507bbb69698d0abaa2c6b3a9674ab4edb0c46595579`.
- SemanticEvidence ID: `ev-2f49b733a85bf5c3eb85bbf5`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,255)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000042",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 255,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c110"></a>

#### C110 — R1-2606780 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-7814cc1e2057fd4083bdb9bb8a3072f439967f337fbb3329aabe4fe8ea461fae`.
- Candidate ID: `proposition-candidate-36a0f1210e091f910aa42a33526a1d54a2f4c2875c7719d7a6442eccd92298df`.
- Review ID: `proposition-review-6e0a4322479d08136f94dcf94055e4afbeb899fb56021958efb240c6b557854f`.
- SourceUnit ID: `proposition-source-865488038e013537351e7c31eea373b091af2572b9f47e6154ad48f6e6e63c78`.
- SemanticEvidence ID: `ev-aaf87fcd799cfbfb59ed06c2`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,191)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000043",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 191,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c111"></a>

#### C111 — R1-2606780 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-0e72749e18ab6f092d12193900e0098c3162300757c2e3684b76944b8b276a16`.
- Candidate ID: `proposition-candidate-40989c08329652c73efbcd68c43653d57919cb3cb5c56aee216354cbbd9cf43e`.
- Review ID: `proposition-review-7e0a5a6d39f358fb06cfad129131b008fd6af31b9f282c4531e093f14b041904`.
- SourceUnit ID: `proposition-source-637ef5dd8ffda26720835d1706bb9b4ce5240f63a2d6c57b2b647a2919dd3f5d`.
- SemanticEvidence ID: `ev-2f7d8d919e23b64249a8bbb6`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,231)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000044",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 447,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c112"></a>

#### C112 — R1-2606780 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-df979e514a7954f2a0fb1e826b9fad21fb844c2e56a8b208fdc4c22b944fe0b3`.
- Candidate ID: `proposition-candidate-331f615951d64d9f178e082e7f9173f6ff5fe54155201a8725d94822bbbd4a18`.
- Review ID: `proposition-review-f91be7c278ec71816c4b053aef2860c0f37ea756f2d0f393c4d7762923c93764`.
- SourceUnit ID: `proposition-source-637ef5dd8ffda26720835d1706bb9b4ce5240f63a2d6c57b2b647a2919dd3f5d`.
- SemanticEvidence ID: `ev-2f7d8d919e23b64249a8bbb6`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[233,447)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000044",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 447,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c113"></a>

#### C113 — R1-2606780 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-cc94dae632209b072ec9e469c503ff2ef6008b100d944568f5e60feecfc34e8d`.
- Candidate ID: `proposition-candidate-0bccac2192c31f4d4d4b0704632b8ed24259ea612adcd8c86160b23a534f1017`.
- Review ID: `proposition-review-674d8ff7d94864293d96ae9d5bfe636d37bfa0e6f3f74f13dc8135d8ff20c987`.
- SourceUnit ID: `proposition-source-9cdb66a5a26f3e3dad4655582865412eeda201a3febc73a357d9a169b3f5305d`.
- SemanticEvidence ID: `ev-a1eda613fd6f7c687639eef8`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,116)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000045",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 263,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c114"></a>

#### C114 — R1-2606780 / OBSERVATION

- AcceptedProposition ID: `accepted-proposition-2e959380168f597aafb86dffef803a89c023092113e653b046d97927da124cab`.
- Candidate ID: `proposition-candidate-2c27c1514d41b248a14819ffa7ba3a9a6c3c851cbbdc086dca5e78688d28aa76`.
- Review ID: `proposition-review-eba71a1de9a0b6fc266b5214df971f7b8b4878194a37fb98beb87a4b9dcfcfc3`.
- SourceUnit ID: `proposition-source-9cdb66a5a26f3e3dad4655582865412eeda201a3febc73a357d9a169b3f5305d`.
- SemanticEvidence ID: `ev-a1eda613fd6f7c687639eef8`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[118,263)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000045",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 263,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c115"></a>

#### C115 — R1-2606780 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-41e1b08781249d6ec8eadc815a3665654f9dd27ba89fbadb004a3a50c760b0a6`.
- Candidate ID: `proposition-candidate-c5af5eafb4be4daefc8e13cc2370ed5e9203aa5c4db8bbac566245ca05236ab7`.
- Review ID: `proposition-review-f8deee7773eeed3b3957ca4417947179975468945818bde1f51c5a878d0502f7`.
- SourceUnit ID: `proposition-source-d7777646c4963ab0855875f2e34ea281fadf47d237c1479ee32832274ddfd34f`.
- SemanticEvidence ID: `ev-08e1f565e15da9fb25483679`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,219)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000046",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 664,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c116"></a>

#### C116 — R1-2606780 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-6ddcc53735f3a53bcf5c7ae538c9bb5e60dd3f2ae4434cb3e48c391c776ef679`.
- Candidate ID: `proposition-candidate-bbef525e2497a5cce7b802e200a28f7a6628198ef9e4f8eab5c3abcab361b43c`.
- Review ID: `proposition-review-9de4578a037c2e561e1c667e6f243967b278959fae0e5acb562aacf35f948376`.
- SourceUnit ID: `proposition-source-d7777646c4963ab0855875f2e34ea281fadf47d237c1479ee32832274ddfd34f`.
- SemanticEvidence ID: `ev-08e1f565e15da9fb25483679`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[220,361)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000046",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 664,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c117"></a>

#### C117 — R1-2606780 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-db87134320383c5028811f21363976974c6b610002823c375dc42d1fdae6fb2d`.
- Candidate ID: `proposition-candidate-e58d8b34f2a542f682e04ff8ea255d09b29786d568c469028d4b7826bf6f93e1`.
- Review ID: `proposition-review-e0f9bcd3ce49b03b8960588e856134a86176f09c0b95c9b7e9acfb0ef97a2956`.
- SourceUnit ID: `proposition-source-d7777646c4963ab0855875f2e34ea281fadf47d237c1479ee32832274ddfd34f`.
- SemanticEvidence ID: `ev-08e1f565e15da9fb25483679`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[363,525)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000046",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 664,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c118"></a>

#### C118 — R1-2606780 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-deb63d360149d02a2ff94b513824d90d7418bef95396f379e1a34dcea0f31929`.
- Candidate ID: `proposition-candidate-9f1d8d5a60a1654f48536c2686c8c4a023b4acd9649682d49c19c222791e00f8`.
- Review ID: `proposition-review-c222cc19ff2e988ee0d7d187d3333821ea32e1a679cfd34caa075df4ecb3b8e8`.
- SourceUnit ID: `proposition-source-d7777646c4963ab0855875f2e34ea281fadf47d237c1479ee32832274ddfd34f`.
- SemanticEvidence ID: `ev-08e1f565e15da9fb25483679`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[527,664)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000046",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 664,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c119"></a>

#### C119 — R1-2606780 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-c518fe055cf47c5384d08cc067153001e11ec4fad2750dde043ce4a7e3678656`.
- Candidate ID: `proposition-candidate-f06582a21090d41f47a1f86233b0fd02a623cd9a5317e6cba8f6505b719836f8`.
- Review ID: `proposition-review-631fd5b8c6ab04fabd1cbf6792be915a9bce1ea403f02082bde5f09b55b1525f`.
- SourceUnit ID: `proposition-source-d100ef40d90d3e845b8ba3ca56a63079331620942cf945c924e82874eab21787`.
- SemanticEvidence ID: `ev-bfefc93ab3507f67a7026407`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,255)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000047",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 326,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c120"></a>

#### C120 — R1-2606780 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-7889eafbfb6ee7dbf1b7b55fc999409db42912b045e4352194bc991437cc5857`.
- Candidate ID: `proposition-candidate-3aec30f38f0463778a95810dd77f39164916e4c758161c850340b091591d9238`.
- Review ID: `proposition-review-dd0b0c567282dc3362f14700ed8f47932896567690fe38783486a9c3d10b0f49`.
- SourceUnit ID: `proposition-source-d100ef40d90d3e845b8ba3ca56a63079331620942cf945c924e82874eab21787`.
- SemanticEvidence ID: `ev-bfefc93ab3507f67a7026407`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[256,326)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000047",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 326,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c121"></a>

#### C121 — R1-2606780 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-6c1a910e77dc7e641dba7c718c06f2882e09b0a8c4a1e54dbb51db179d1748bf`.
- Candidate ID: `proposition-candidate-dee3dd6431d1b159d91d67732911605d3fedf2cc985acf7c297e6077c180d39b`.
- Review ID: `proposition-review-e85f5b50b773ae45fbcfce84dec052a667082d9d888f94579ca90a33e789ea7b`.
- SourceUnit ID: `proposition-source-b775f657173ebd31969281cfed05f02f9ac6f5739fb4b27010b9d406e5d261ec`.
- SemanticEvidence ID: `ev-55a5c5d78bb0540639a1efb9`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[0,83)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000048",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 127,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

<a id="ap-c122"></a>

#### C122 — R1-2606780 / PROPOSAL

- AcceptedProposition ID: `accepted-proposition-78043b68747a28a3f8da48799177e10eae06a786c98d1068f1a3da03138b84de`.
- Candidate ID: `proposition-candidate-505eaf5f3620918788f391a2f12e6ad2333987823b2c93511d88ba3a14a9f1c6`.
- Review ID: `proposition-review-0d13aecfd8f473a475ad07cdea86d90419477af7d6a1b9c9ce2a13a0a949afc3`.
- SourceUnit ID: `proposition-source-b775f657173ebd31969281cfed05f02f9ac6f5739fb4b27010b9d406e5d261ec`.
- SemanticEvidence ID: `ev-55a5c5d78bb0540639a1efb9`.
- Organization metadata: Ericsson.
- Meeting: RAN1 #126; scope: `contribution`.
- Accepted source span: `[85,127)`.
- Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<details><summary>전체 EvidenceRef / source span</summary>

```json
[
  {
    "evidence_ref": {
      "tdoc_id": "R1-2606780",
      "working_group": "RAN1",
      "meeting": "126",
      "member": "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx",
      "block_id": "b000048",
      "block_type": "paragraph",
      "heading_path": [
        "Conclusion"
      ],
      "page": null,
      "sheet": null
    },
    "sequence": 0,
    "char_start": 0,
    "char_end": 127,
    "row_index": null,
    "cell_index": null
  }
]
```

</details>

### 원문 checksum과 normalization identity

아래 값은 보고서 작성 시 읽은 실제 raw 파일과 receipt에서 확인했다. Receipt가 없는 경우 raw SHA-256은 실제 파일에서 계산한 값이며 normalization identity를 추정하지 않았다.

<details><summary>R1-2603495 — source identity</summary>

- Raw SHA-256: `d8b75cdf807725e465ed188996baa6ad6b1f7edfc631d88802baad8e57476838`.
- Normalized checksum: `95ffb8eaa6da4dc9e12351a37efa9692dcf7db3c21099fa067ea96f34cbe3fed`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "d8b75cdf807725e465ed188996baa6ad6b1f7edfc631d88802baad8e57476838",
  "parser_members": {
    "R1-2603495(R2-2602815).docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2603620 — source identity</summary>

- Raw SHA-256: `ab69cd1149b69c24333832a867402d9bf75e84cd727febd4d1cc5f175c442e4f`.
- Normalized checksum: `57dd018178e678a07742658e3dca5921682d3372debf940608983867404dd8e1`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "ab69cd1149b69c24333832a867402d9bf75e84cd727febd4d1cc5f175c442e4f",
  "parser_members": {
    "R1-2603620_Discussion on contention based PUSCH transmission.docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2603671 — source identity</summary>

- Raw SHA-256: `b4b0f8cd0431ae1cec327249e6f555dab7777d41c3de18cf4bf07210448b5da5`.
- Normalized checksum: `b79a56e7b387635f9de807c16237d24aed4be144d3e39b2ad72f363924a5c393`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "b4b0f8cd0431ae1cec327249e6f555dab7777d41c3de18cf4bf07210448b5da5",
  "parser_members": {
    "R1-2603671.docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2603673 — source identity</summary>

- Raw SHA-256: `e710e60f1737a76dc12c09beeeb6455239ca3e80c89bd8d5f478ea64caab611f`.
- Normalized checksum: `bb48461b06a0e6dc946891bcdf3dc08d9f319472c5295cf28d30326b8f032bb9`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "e710e60f1737a76dc12c09beeeb6455239ca3e80c89bd8d5f478ea64caab611f",
  "parser_members": {
    "R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2603806 — source identity</summary>

- Raw SHA-256: `3286367a3e07085f418f81f76e26c07578e60864ca1d85b0d600e298f53ea696`.
- Normalized checksum: `10a1d4ac1c0259145919e46f358bd5deb82723ca462e92b2ed8a147e1b4395a8`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "3286367a3e07085f418f81f76e26c07578e60864ca1d85b0d600e298f53ea696",
  "parser_members": {
    "R1-2603806.docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2603807 — source identity</summary>

- Raw SHA-256: `01ad8099522a56d0982c87916e908b5576dbdecef2076d88827cc40248fcf02d`.
- Normalized checksum: `7d27ad4c8d931e423b83b53999354d68de669253c538df4511650b1a1aef0b44`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "01ad8099522a56d0982c87916e908b5576dbdecef2076d88827cc40248fcf02d",
  "parser_members": {
    "R1-2603807.docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2603957 — source identity</summary>

- Raw SHA-256: `582c71e1d8a0bcc395e3143370d15d4f57fa8facb27c51d432de6405b6a097be`.
- Normalized checksum: `ac39fcfbc4e3e6a9669df9d7e52dc01ad4cc756ca77435f94aa186b616ce3a44`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "582c71e1d8a0bcc395e3143370d15d4f57fa8facb27c51d432de6405b6a097be",
  "parser_members": {
    "R1-2603957.docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2604082 — source identity</summary>

- Raw SHA-256: `5f176b79e81c4d5344b16d052cde79c113d80fc86db505e9e2d5a3472aaba6bd`.
- Normalized checksum: `9ceffb7310338057cfe71a4ae1e2c98d2c485d81cdef906532a801f457a38d64`.
- Receipt extraction status: `unsupported_format`.

```json
{
  "raw_sha256": "5f176b79e81c4d5344b16d052cde79c113d80fc86db505e9e2d5a3472aaba6bd",
  "parser_members": {
    "R1-2604082 [Draft] Reply LS on evaluation assumptions for contention based PUSCH transmission.doc": "unsupported"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2604097 — source identity</summary>

- Raw SHA-256: `f229dfc50e2810c26b815428053b51547118768cccafa6c7a437ba1cbbd22b82`.
- Normalized checksum: `499a324a845e64d927eb0ec249ae54ae383dd84933d3cbf6b49e179e11104bd0`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "f229dfc50e2810c26b815428053b51547118768cccafa6c7a437ba1cbbd22b82",
  "parser_members": {
    "R1-2604097/R1-2604097 Discussion on LS on evaluation assumptions for contention based PUSCH transmission-v2.docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2604147 — source identity</summary>

- Raw SHA-256: `a96da6a5e6510f52e6827aff1469b2e8b80ac0d1d72128258d7e9b4c2119ac5b`.
- Normalized checksum: `819d0e8121498d268d0631ac72bbbccc244d1b6bc8116d83911bc8aba804c1a2`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "a96da6a5e6510f52e6827aff1469b2e8b80ac0d1d72128258d7e9b4c2119ac5b",
  "parser_members": {
    "R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2604209 — source identity</summary>

- Raw SHA-256: `7600150a08f37a3546bfca3a965080a2764eb4c94e7b15073837c258712edfd4`.
- Normalized checksum: `d6b00a99e6d37a3613b40aabdc73c06714d60c17604265ddf616d3a049e0a868`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "7600150a08f37a3546bfca3a965080a2764eb4c94e7b15073837c258712edfd4",
  "parser_members": {
    "R1-2604209 Discussion on Reply LS on evaluation assumptions for contention based PUSCH transmission.docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2604529 — source identity</summary>

- Raw SHA-256: `5d22a76efc1d50f07612cd6430c31457621b8aeba46d98098e09c0a6ade90cfd`.
- Normalized checksum / normalization identity: not locally resolved.

</details>

<details><summary>R1-2604657 — source identity</summary>

- Raw SHA-256: `05be281b5617ca3747a36a7b5e7ddee0d0809c830cd2c0db57c3fcfcd28037f6`.
- Normalized checksum / normalization identity: not locally resolved.

</details>

<details><summary>R1-2604920 — source identity</summary>

- Raw SHA-256: `7a30e0dae5fdc1cbf5cbdf1e62057bc192ad76ad39897aac8caf30393a1f089c`.
- Normalized checksum: `aef736530743f19e8738bb8abd1e3dd13eeebeaf0bfbf776c14de06ddafa6a9f`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "7a30e0dae5fdc1cbf5cbdf1e62057bc192ad76ad39897aac8caf30393a1f089c",
  "parser_members": {
    "R1-2604920.docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2605343 — source identity</summary>

- Raw SHA-256: `73f0fe5662048eb0511811283133d437985a5c5790ba0d9779ad166ea348ee06`.
- Normalized checksum: `42e1492e4b4761e0c7e1096cda863214ac05b5d07fcca7cf380e248d5b41011d`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "73f0fe5662048eb0511811283133d437985a5c5790ba0d9779ad166ea348ee06",
  "parser_members": {
    "R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2606317 — source identity</summary>

- Raw SHA-256: `26de4beab26335344efa95b7adf9297e3cba1ba12f6691c4a90c6f3bcee669b1`.
- Normalized checksum / normalization identity: not locally resolved.

</details>

<details><summary>R1-2606713 — source identity</summary>

- Raw SHA-256: `a8f0d528e655c5712f928ad705785b2edf7982e7b208790dfb0e1322fef85b30`.
- Normalized checksum: `8c9c89bb4149e587eb7d5fc457816e9a763a48ff8c3146843209d3bb079d3c43`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "a8f0d528e655c5712f928ad705785b2edf7982e7b208790dfb0e1322fef85b30",
  "parser_members": {
    "R1-2606713.docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

<details><summary>R1-2606780 — source identity</summary>

- Raw SHA-256: `f4fb815dfda21d6e5a8af12dd5bf8d6385b9debed6a53fbb10550272202cb768`.
- Normalized checksum: `3e88353f296c2998925b6328c43a2832cf5c55677fe7bfbfc3cc192685339cef`.
- Receipt extraction status: `parsed`.

```json
{
  "raw_sha256": "f4fb815dfda21d6e5a8af12dd5bf8d6385b9debed6a53fbb10550272202cb768",
  "parser_members": {
    "R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx": "docx@1"
  },
  "normalized_schema_version": "1"
}
```

</details>

## 6. 미검사 TDoc / Evidence Gap

아래 네 문서는 **현재 로컬 contribution inspection이 완료되지 않아 회사 주장 분석에서 제외되었다.** 해당 회사가 기술 제안을 하지 않았다는 뜻이 아니다. Metadata 제목이나 Chair Note, 이웃 contribution에서 내용을 보완 추론하지 않았다.

| TDoc | 조직 | Meeting | 현재 실패 내역 | 원문 상태 |
|---|---|---|---|---|
| R1-2604082 | ZTE Corporation, Sanechips | RAN1 #125 | normalization_failed; receipt: unsupported_format. Member가 legacy .doc이며 warning은 unsupported member format. | [로컬 raw ZIP 존재](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604082/R1-2604082.zip>) |
| R1-2604529 | Fainity Innovation | RAN1 #125 | normalization_failed; 기존 실행 오류: `File is not a zip file`. 현재 normalization receipt 없음. | [로컬 raw ZIP 존재](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604529/R1-2604529.zip>) |
| R1-2604657 | Google | RAN1 #125 | normalization_failed; 기존 실행 오류: `File is not a zip file`. 현재 normalization receipt 없음. | [로컬 raw ZIP 존재](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604657/R1-2604657.zip>) |
| R1-2606317 | Fainity Innovation | RAN1 #126 | normalization_failed; 기존 실행 오류: `File is not a zip file`. 현재 normalization receipt 없음. | [로컬 raw ZIP 존재](</home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2606317/R1-2606317.zip>) |

실패 정보는 현재 저장된 [V0.11 completion result](</home/jjuns/3gpp-study-engine/data/derived/topic-completion/ran1/topic-completion-plan-52f68ed8910703c92c29d7ed2cd58e1c3b6d43f68d7313fbe2490a0d484b5b4c/results/topic-completion-result-921abb07d2d038ea7b027f37063e64ec799c37e6c521b3db0121d25b8cfe8a8a.json>) 및 해당 receipt에서 확인했다. 이번 작업에서는 재수집·정규화 재시도·파서 수정 없이 현재 공백을 유지했다.

검사 완료 14개 중 5개(R1-2603495, R1-2603671, R1-2603807, R1-2603957, R1-2606713)는 기존 규칙이 추출한 contribution SemanticEvidence가 0개다. 또한 R1-2603806의 후보는 모두 연구자 결정으로 제외되었다. 이 여섯 문서도 승인 근거에 의한 기술 주장 요약에는 쓰이지 않았지만, 원문 파일 인덱스에서 누락하지 않았다.

## 7. 해석 시 주의사항

- Contribution의 Proposal·Observation·Conclusion을 그대로 구분했다. Conclusion이나 Observation을 Proposal로 바꾸지 않았다.
- 원문 속 “RAN1 agreed”, “RAN1 clarifies”, “under discussion”은 해당 contribution의 서술이다. 독립적인 meeting-authority 검증이나 채택 증거로 승격하지 않았다.
- 전용·공유 DMRS, 동일 DMRS·시간/주파수 자원, 강한 간섭, 다중 안테나 수신, MMSE IRC, initial transmission·reattempt, 낮은 residual BLER, 높은 부하·작은 TB의 조건을 해당 요약에 보존했다.
- 연구자 승인 단위는 회사 전체 입장이나 기술적 진실을 보증하지 않는다. 반복 문구나 proposition 수로 지지·중요도·다수 선호·consensus를 추론하지 않았다.
- 이 회사 간 proposition relation은 아직 V0.13 review되지 않았다. Formal EQUIVALENT·OVERLAPPING·DISTINCT·CONFLICTING·NOT_COMPARABLE을 생성하거나 주장하지 않았다.
- Chair Note 부재는 부정적 증거가 아니며, 선택된 Chair Note와 로컬 corpus의 완전성을 가정하지 않는다.
- 이 보고서의 기술 쟁점 분류는 Markdown에서만 사용했다. Profile·V0.12 review·V0.13 상태·source code를 변경하지 않았다.

검증: 70개 승인 span을 실제 SourceUnit·CONTRIBUTION SemanticEvidence와 대조했고, 모든 로컬 링크의 파일 존재를 확인했다. 승인 span의 EvidenceKind와 EvidenceRef를 유지했다. 네 미검사 TDoc을 coverage gap으로 남겼다. 작성 전후 runtime 파일 checksum을 대조하여 source·review 상태가 바뀌지 않았음을 확인했다.
