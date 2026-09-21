# Contention-based PUSCH: RAN1 #125–#126 기술 검토

## 핵심 요약

여러 UE가 같은 시간·주파수 자원으로 BSR을 보낼 때, 무엇으로 UE를 구별하고 어느 조건에서 payload를 복호할 수 있는지가 중심 질문이다.

- **시간·주파수 중첩이 곧 복호 실패인가?** NEC는 공간·코드 영역의 분리 가능성을, Spreadtrum/UNISOC는 직교 DMRS를 설명한다. vivo와 Huawei/HiSilicon은 DMRS 설계와 UE 간 채널 상관 조건을 함께 확인해야 한다고 서술한다. [NEC](#s-r1-2603806), [Spreadtrum/UNISOC](#s-r1-2603671), [vivo](#s-r1-2603620), [Huawei/HiSilicon](#s-r1-2604920)
- **UE 식별과 payload 복호의 조건은 같은가?** Ericsson은 dedicated/shared DMRS와 RNTI 조합에 따른 복호 시도 수를 구분한다. Samsung은 DMRS 검출 오류와 MMSE-IRC 수신 성능을 별도로 평가해야 한다고 제안한다. [Ericsson](#s-r1-2603673), [Samsung](#s-r1-2604147)
- **재시도와 부하를 어떻게 반영해야 하는가?** Ericsson의 #126 수정 문서는 동일 DMRS 충돌 시 초기 복호 성공률을 약 40%로 서술하고, 재시도 시 낮은 잔여 BLER가 가능하다고 설명한다. Samsung의 early BSR 효용 주장은 부하·TB 크기·첫 송신 조건을 따로 가진다. [Ericsson 수정 문서](#s-r1-2606780), [Samsung](#s-r1-2604147)

범위는 RAN1 #125–#126에서 선택한 관련 문서 18개이며, 이 중 14개의 본문을 읽었다. 여기에는 연구 질문을 보낸 RAN2 LS도 포함된다. 나머지 네 문서의 기술 내용은 확인하지 못했다. 아래 설명은 읽은 기고서와 선택한 Chair Note에 한정한다.

<a id="research-question"></a>
## 연구 질문: RAN2는 무엇을 물었는가?

RAN2가 보낸 [R1-2603495 / R2-2602815](#s-r1-2603495)는 여러 UE가 같은 시간·주파수 자원을 선택했을 때 네트워크가 UE를 구별하고 payload를 복호할 수 있는지 묻는다. LS는 자원 효율과 지연을 기존 SR/BSR 절차와 비교하는 평가를 설명한다. 시작 가정에는 1 또는 2 PRB와 QPSK, dedicated/shared DMRS, C-RNTI/common RNTI, 충돌 해결 실패 후 새 전송으로 재시도하는 절차가 들어 있다.

이 LS의 “같은 시간·주파수 자원과 같은 DMRS sequence를 선택하면 충돌한 모든 PUSCH가 실패한다”는 문장은 **평가를 위한 가정**이다. LS 자체가 그 조건에서의 실제 UE 구별·복호 가능성을 RAN1에 묻는다. 이 문서는 OPPO의 회사 제안이나 RAN1 #125의 최종 결론을 뜻하지 않는다. Source: “1 Overall description”, “2 Actions”.

## Company Contribution — 기술 질문별 기고 내용

<a id="separation"></a>
### 1. 같은 시간·주파수 자원을 써도 UE를 구별할 수 있는가?

**Spreadtrum/UNISOC — R1-2603671.** 회신 초안은 여러 UE의 DMRS가 서로 직교하면 네트워크가 UE별 채널을 추정하고 데이터를 따로 복호할 수 있다고 설명한다. 구별 가능한 UE 수는 직교 DMRS sequence 수의 제한을 받는다. 문서의 “RAN1 confirm”은 제출된 회신 초안의 문구다. [Source: “Reply to Question”](#s-r1-2603671)

**NEC — R1-2603806, R1-2603807.** R1-2603806의 Proposal 1은 시간·주파수 충돌이 있더라도 공간 또는 코드 영역에서 신호를 분리할 수 있으면 UE 구별과 복호가 가능하다는 답변을 제안한다. 공간 영역 설명은 충분히 다른 입사각과 직교성이 있는 채널·수신 빔을 조건으로 둔다. 코드 영역 설명은 서로 다른 DMRS sequence와 데이터 심벌의 OCC를 예로 든다. R1-2603807의 회신 초안에도 같은 조건부 설명이 있다. [Source: “Discussion on the LS reply”, Proposal 1](#s-r1-2603806), [“1. Overall Description”](#s-r1-2603807)

**vivo — R1-2603620.** 본문은 직교 DMRS뿐 아니라 UE 채널 벡터 사이의 충분히 낮은 상관도 필요하다고 설명한다. 같은 DMRS port에서 scrambling ID만 바꾼다고 안정적인 채널 추정과 복호가 보장되지는 않는다고 서술한다. Observation 2는 UE 식별·복호가 아직 연구 중인 UL DMRS 설계에 크게 의존한다고 정리한다. [Source: “DMRS”, “Scrambling ID”, Observation 2](#s-r1-2603620)

**Xiaomi — R1-2603957.** 회신 초안은 충돌 UE의 식별·복호 확률이 송신 측 처리, blind MMSE detection·equalization·decoding 같은 수신 처리에 따라 달라질 수 있다고 설명한다. 같은 처리를 적용하더라도 near-far 효과와 수신 안테나 수가 영향을 준다고 서술한다. 특정 복호 성공률을 보장하는 설명은 아니다. [Source: “1 Overall description”, “Regarding the question from RAN2” 문단](#s-r1-2603957)

**Huawei/HiSilicon — R1-2604920.** 직교 DMRS port를 쓰더라도 UE 채널 상관이 높으면 PUSCH의 port/layer 간 간섭이 남을 수 있다고 설명한다. 네트워크가 MU pairing으로 UE 조합을 고르는 경우와 구분하여, DMRS 충돌 확률뿐 아니라 이 간섭도 payload 복호 평가에 반영하도록 제시한다. [Source: “Relevant aspects of DMRS design in RAN1”](#s-r1-2604920)

<a id="dmrs-capacity"></a>
### 2. Dedicated/shared DMRS와 UE ID는 어떤 역할을 하는가?

**Ericsson — R1-2603673.** 문서는 다음 구성을 구분한다. N은 서로 다른 DMRS 구성 수이고 M은 자원을 공유하는 UE 수다. [Source: “Discussion”, Observation 1·4](#s-r1-2603673)

| 구성 | 문서가 설명하는 조건 |
|---|---|
| UE별 dedicated DMRS | 강하게 간섭하는 UE에 N개 DMRS를 일대일 배정하면 같은 자원에 다중화할 수 있는 UE 수는 최대 N이다. 충분한 수신 안테나 수와 SINR도 필요하다. |
| Shared DMRS | 더 많은 UE가 자원을 공유할 수 있지만 같은 DMRS를 고를 확률이 제한 요인이다. 충분한 수신 안테나와 SINR 조건에서 서로 다른 DMRS의 동시 전송을 복호할 수 있다고 설명한다. |
| Dedicated DMRS + C-RNTI | N개 DMRS–C-RNTI 조합이면 N번의 복호 시도를 설명한다. 서로 다른 scrambling은 DMRS 직교성을 제한할 수 있다. |
| Shared DMRS + common RNTI + payload UE ID | M이 N보다 훨씬 커도 DMRS별 N번의 blind decoding을 설명한다. UE ID 확인은 payload 복호에 의존한다. |
| Shared DMRS + UE별 C-RNTI | N개 DMRS와 M개 C-RNTI 조합을 확인하면 복호 가설 수가 M×N이 된다. |

vivo도 payload의 UE ID는 PUSCH를 성공적으로 수신·복호한 뒤에 읽을 수 있다고 설명한다. UE ID를 넣는 것 자체가 충돌한 신호의 채널 추정이나 분리를 해결하는 것은 아니다. [Source: R1-2603620, “UE ID”](#s-r1-2603620)

<a id="nr-starting-point"></a>
**Ofinno — R1-2604209.** NR 구성을 연구 출발점으로 설명하면서, MsgA PUSCH는 서로 다른 preamble을 선택하는 조건에서 최대 4개 직교 DMRS와 잠재적인 4 UE 구별을 언급한다. CG PUSCH에서는 enhanced double-symbol Type 2 DMRS의 24개 직교 port와 Type-1 CG의 5-bit port 지시 제약을 구분한다. 해당 구성에서 port 0–13에 따른 최대 14 UE 가능성을 설명한다. Observation 2와 Annex는 해당 blind detection 성능과 실제 지원 UE 수에 추가 연구가 필요하다고 명시한다. 이 숫자는 contention-based PUSCH에서 검증된 수용 UE 수가 아니다. [Source: “Question 1”, Case 1·2, Observation 2](#s-r1-2604209)

<a id="blind-decoding"></a>
### 3. 어떤 수신기와 검출 가정으로 비교해야 하는가?

**OPPO — R1-2604097.** 본문은 ① DMRS만 사용하는 방식, ② DMRS와 scrambling code를 사용하는 방식, ③ 여기에 MCS/TBS를 더하는 방식을 비교한다. Observation 3은 지원하려는 충돌 UE 수가 늘어나는 구성에서 blind decoding 복잡도가 증가하고 검출 확률이 낮아지는 경향을 제시한다. Observation 2는 다른 DMRS port를 사용할 때의 검출 확률이 다른 sequence만 사용할 때보다 높다고 서술하되, UE별 채널 상태에 의존한다고 한정한다. 이는 OPPO 문서의 분석이다. [Source: “Blind decoding complexity analysis”, “Detection probability of colliding PUSCHs”](#s-r1-2604097)

<a id="receiver-assumptions"></a>
Samsung과 Ericsson의 수신 성능 설명은 평가 조건을 함께 읽어야 한다.

| Source | 본문에서 확인한 조건 | 문서가 제시하는 설명 |
|---|---|---|
| Samsung R1-2604147, Figures 1·2 및 Appendix | 5G NR PUSCH 구조, 예시 1 PRB·14 symbols·Type 1 DMRS 1 symbol. Figure 1은 UE 1개·충돌 없음·false alarm 1%. Figure 2는 완벽한 DMRS 식별을 가정. Appendix는 2Rx, TDL-C | 검출 누락·오검출과 payload 복호를 구분한다. Proposal 1은 두 단계의 상세 평가 가정을 정의하자고 제안한다. |
| Ericsson R1-2603673, Figure 1 | 4 Rx chains, TDL-A, MMSE-IRC, 해당 PUSCH의 DMRS를 이상적으로 알고 있음, UE별 동일 송신 전력·단일 port | 다른 DMRS를 쓰는 동시 전송의 BLER를 설명하며 서로 다른 port와 서로 다른 sequence를 구분한다. |
| Ericsson R1-2605343·R1-2606780, Figures 1·2 | 4 또는 32 Rx chains, CDL-A, MMSE-IRC, 이상적인 DMRS 지식, UE별 동일 송신 전력·단일 port | 다중 안테나 수신과 DMRS 구성에 따라 동시 전송을 복호할 수 있는 조건을 설명한다. |

[Source: Samsung](#s-r1-2604147), [Ericsson #125](#s-r1-2603673), [Ericsson #126](#s-r1-2605343), [Ericsson 수정 문서](#s-r1-2606780)

Samsung의 Observation 2는 같은 DMRS를 고르면 식별이 실패하고, 같은 PUSCH 자원을 쓰는 두 UE 이상에 대해서는 직교 DMRS 선택 여부와 관계없이 MMSE-IRC 복호 실패가 예상된다고 서술한다. 앞 문단은 채널 행렬의 ill-conditioning과 동적 UE 선택 부재를 논거로 든다. 또한 중첩 PUSCH의 상세 시뮬레이션 가정이 없어 관련 BLER 결과를 제공하지 않았다고 명시한다. 따라서 이를 Ericsson의 다른 조건에서 얻은 BLER 결과와 동일 조건의 검증 결과처럼 비교하지 않는다. [Source: R1-2604147, Observation 2와 바로 앞 문단](#s-r1-2604147)

<a id="retries"></a>
### 4. 같은 DMRS로 충돌한 초기 전송과 재시도는 어떻게 다른가?

Ericsson의 #126 문서는 같은 시간·주파수 자원과 같은 DMRS에서의 시스템 수준 평가를 따로 설명한다. [Source: R1-2605343](#s-r1-2605343), [R1-2606780](#s-r1-2606780)

| 문서 | 초기 전송 설명 | 재시도 설명과 한계 |
|---|---|---|
| R1-2605343, Figure 3·Observation 5 | 성공률이 일반적으로 절반 미만이라고 서술한다. | 재시도로 낮은 잔여 BLER를 얻을 수 있다는 관찰에서 random backoff가 불필요할 가능성을 제시한다. |
| R1-2606780, Background·Figure 3·Observation 5 | R1-2605343의 Figure 3 결과를 수정한 문서라고 명시한다. 초기 성공률은 일반적으로 약 40%라고 서술한다. | 본문은 재시도 증가 시 성공률이 90%대 후반일 수 있다고 설명한다. 재충돌 가능성이 낮아진다는 설명을 바탕으로 backoff 불필요 가능성을 제시한다. |

두 문서의 Proposal 2는 초기 전송과 재시도를 구분한 결과를 RAN2에 알리자는 제안이다. 재시도 횟수와 시스템 부하에 따른 설명이므로 “모든 충돌은 복호 가능” 또는 “backoff는 항상 불필요”로 일반화하지 않는다. R1-2606780의 Proposal 2에는 “초기 전송의 절반 미만”, Observation 5에는 “약 40%”라는 표현이 각각 남아 있다.

<a id="load-benefit"></a>
### 5. Early BSR의 이점은 부하와 TB 크기에 어떻게 의존하는가?

**Samsung — R1-2604147.** Observation 3은 낮거나 중간인 시스템 부하에서는 early BSR의 실익이 거의 없다고 서술한다. 높은 부하에서 작은 TB의 첫 송신에는 도움이 될 수 있다고 한정한다. Observation 4는 높은 부하와 작은 TB를 갖는 트래픽 도착 조건에 평가를 집중할 수 있다고 제시한다. [Source: “Analytical ‘best-case’ scenario for BSR via CB-PUSCH”, Observation 3·4](#s-r1-2604147)

같은 문서의 Table 1은 36 UE가 자원을 공유하고 직교 DMRS 4개를 사용하며, 균일한 무작위 도착과 검출 오류가 없는 이상적 조건을 놓는다. DDDDU와 30 kHz SCS의 예시에서 송신 기회 간격은 2.5 ms다.

| UE별 한 송신 기회의 BSR 발생 확률 | 해당 예시의 평균 발생 간격 | DMRS 충돌 확률 | 아무 UE도 BSR을 보내지 않을 확률 |
|---|---|---|---|
| 1/400 | UE당 1초 | 0.1% | 91.4% |
| 1/100 | UE당 250 ms | 1.5% | 69.6% |

표의 충돌 확률은 검출 누락이나 오검출을 포함하지 않는다. 매우 낮은 도착률에서 충돌이 적다는 설명과 높은 부하에서의 early BSR 필요성을 함께 읽어야 한다. 이 표를 다른 UE 수·도착 분포·수신기에 그대로 적용하지 않는다. [Source: Table 1 및 Observation 5](#s-r1-2604147)

또한 Observation 6은 자원 낭비, 오검출에 따른 HARQ 처리 문제, 실제 TB가 없을 때의 불필요한 복호가 해결되지 않으면 필수 UL 요청 기능을 CG-PUSCH에 의존시키는 것을 피해야 한다고 서술한다. 이는 해당 기고서의 운용상 문제 제기다. [Source: “Base station complexity for CG-PUSCH receptions”](#s-r1-2604147)

<a id="assumptions"></a>
### 6. 평가 가정과 RAN2 회신에서 무엇을 더 정해야 하는가?

**Huawei/HiSilicon — R1-2604920.** 문서는 PUSCH 시작 심벌, 심벌 수, 슬롯 경계 횡단 가능성을 먼저 논의하도록 제시한다. DMRS port 수와 UE 배정, 채널 상관 모델도 필요하다고 설명한다. UE 전용 preamble은 DMRS 외에 검토 중인 방법으로 소개한다. RAN2 회신은 PUSCH·DMRS 관련 가정과 평가 관찰이 정리될 때까지 미루자고 제안한다. [Source: PUSCH time domain·DMRS design 절, “Position in RAN1 to RAN2 LS”](#s-r1-2604920)

**vivo — R1-2603620.** Proposal 2는 평가 가정과 규격 영향을 포함한 연구를 계속한다는 내용을 RAN2에 알리자고 제안한다. Proposal 3은 UL DMRS 설계가 분명해진 이후에 UE 구별 질문에 답하자는 내용이다. [Source: “Suggested response to RAN2”, Proposal 2·3](#s-r1-2603620)

**Ericsson — R1-2603673, R1-2605343, R1-2606780.** 각 문서의 Table 1을 시뮬레이션 출발점으로 삼고 RAN2에 확인하자고 제안한다. #125 문서는 payload를 64 bits로, #126의 두 문서는 56 bits로 제시한다. 세 표는 매 UL slot의 송신 기회, 요구 BLER 1% 또는 10%, 재시도 사이 최소 4 slots(TDD) 또는 7 slots(FDD)를 적는다. 이를 하나의 확정된 공통 가정으로 합치지 않는다. [Source: #125 Table 1·Proposal 2](#s-r1-2603673), [#126 Table 1·Proposal 3](#s-r1-2605343), [수정 문서 Table 1·Proposal 3](#s-r1-2606780)

<a id="draft-126"></a>
**Huawei/HiSilicon — R1-2606713.** #126 회신 초안의 표는 UMa, 2 GHz, 32R, FTP3의 평균 도착 간격 100 ms·packet 100 KB, 10–100 CONNECTED UE 등의 시스템 수준 조건을 담는다. CB-BSR에는 2 RB·14 symbols와 NR Type 1 DMRS의 4 ports를 적는다. 공통 pool에서 port를 고르는 구성과 단일 port 배정 구성을 제시하며, 같은 DMRS 충돌은 복호 불가로 두고 다른 DMRS의 복호는 BLER 곡선에 따르도록 적는다. contention resolution timer 10 slots와 추가 backoff [1–20 ms]도 표에 있다.

이 초안은 충돌 시 식별·복호 확률에 추가 평가가 필요하다고 서술한다. 본문의 “RAN1 agreed”와 Source의 “[To be RAN1]”은 회신 초안에 있는 표현이다. 여기서는 Huawei/HiSilicon이 제출한 초안의 내용으로만 보고한다. [Source: “1 Overall description”, SLS assumption table와 마지막 문단](#s-r1-2606713)

## Meeting Discussion — 선택한 Chair Note의 기록

<a id="discussion-125"></a>
### RAN1 #125

선택한 Chair Note는 R1-2603495의 질문을 소개하고, RAN1 연구의 일부로 다루며 결론을 얻은 뒤 답변한다는 문구를 기록한다. 논의 위치를 AI 10.5.5로 지정한다. 이어지는 “Relevant tdocs” 구간에는 vivo, Spreadtrum/UNISOC, Ericsson, NEC, Xiaomi, OPPO, Samsung, Huawei/HiSilicon, Ofinno 등의 문서명이 적혀 있다. 이는 이 Chair Note에서 확인한 논의 맥락이다. [Source: #125 Chair Note, R1-2603495와 “Relevant tdocs”](#s-chair-125)

<a id="discussion-126"></a>
### RAN1 #126

선택한 Chair Note의 “CB-PUSCH” 구간은 R1-2606713을 적고 RAN2 LS R1-2603495의 후속 논의를 AI 10.5.5에서 계속한다고 기록한다. R1-2605343 옆의 설명도 같은 항목에서 연구를 계속하며 즉각적인 조치는 없다고 적는다. [Source: #126 Chair Note, “CB-PUSCH” 및 R1-2605343 항목](#s-chair-126)

같은 Chair Note의 “Other physical layer signals, channels and procedure” 절은 **“R1-2603495의 요청에 따른 CB PUSCH for BSR”**을 명시한다. 그 절의 Agreement 표에는 다음 LLS 조건이 적혀 있다.

| 항목 | 선택한 Chair Note에 기록된 내용 |
|---|---|
| 자원·payload | 2 RB·14 symbols를 출발점으로 사용하고 다른 값도 보고 가능. Payload는 56·64·112 bits 중 선택하며, 112 bits에는 RB 배정도 보고 |
| UE·채널 | 동시 UE 1–4개. CDL-A 또는 TDL-A와 선택 내용을 보고. 무작위·낮은 상관·높은 상관의 세 경우 및 세부 가정 보고 |
| 안테나·수신기 | UE 1Tx, BS 4·8·64 Rx, 현실적인 채널 추정, MMSE-IRC |
| DMRS·SNR | Rel-15 NR Type 1 DMRS와 port 수 등 구성을 보고. 동일 또는 비동일 UE별 SNR과 분포 세부사항 보고 |
| 결과 | 단일 UE 대비 1%·10% BLER에서의 손실, DMRS 누락·오검출률 등. 결과표에는 DMRS blind detection 적용 여부를 명시 |

이 표는 위 R1-2606713의 SLS 회신 초안 표와 다른 자료다. 여기서는 Chair Note에 기록된 평가 맥락을 설명한다. Agreement·Conclusion 표제를 독립적인 최종 회의 결과로 승격하지 않는다. [Source: #126 Chair Note, “Support the following EVM of LLS for evaluating CB PUSCH” 및 결과 보고 표](#s-chair-126)

<a id="meeting-outcome"></a>
## Meeting Outcome — 권한 있는 회의 보고서로 확인한 결과

이번에 읽을 수 있는 자료에는 RAN1 #125와 #126의 해당 결과를 확인할 권한 있는 회의 보고서·minutes가 없다. 따라서 회사 기고서의 Proposal, 회신 초안의 “RAN1 agreed”, Chair Note의 Agreement 표제를 #125–#126의 확정된 회의 결과로 제시하지 않는다. 이는 결과가 없거나 제안이 거절되었다는 뜻이 아니다.

## Open Issue / Evidence Gap

기술적으로 남는 질문은 DMRS 검출과 payload 복호를 어떤 채널·수신기 조건에서 평가할지, 같은 DMRS 충돌 후 재시도를 어떻게 모델링할지, 높은 부하·작은 TB 조건에서의 이점을 어떤 기준선과 비교할지이다. 각 문서의 조건을 맞춘 추가 검토가 필요하며, 이 보고서는 시뮬레이션을 재현하지 않았다.

다음 네 문서는 목록과 로컬 원본을 확인했지만 본문을 읽지 못했다. 해당 조직의 기술 주장은 이 보고서에 채워 넣지 않았다.

| 문서 | 조직 / 회의 | 읽기 제한 | 원본 |
|---|---|---|---|
| R1-2604082 | ZTE Corporation, Sanechips / #125 | 지원되지 않는 `.doc` 본문 형식 | [공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604082.zip)  · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2604082/R1-2604082.zip) |
| R1-2604529 | Fainity Innovation / #125 | 현재 준비된 자료에서 본문을 읽을 수 없음 | [공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604529.zip)  · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2604529/R1-2604529.zip) |
| R1-2604657 | Google / #125 | 현재 준비된 자료에서 본문을 읽을 수 없음 | [공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604657.zip)  · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2604657/R1-2604657.zip) |
| R1-2606317 | Fainity Innovation / #126 | 현재 준비된 자료에서 본문을 읽을 수 없음 | [공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Docs/R1-2606317.zip)  · [로컬 ZIP](../data/raw/tdocs/ran1/126/R1-2606317/R1-2606317.zip) |

선택본의 `eom`·`eom1` 파일명은 최종본임을 보증하지 않는다. 선택한 Chair Note에 문서가 보이지 않는 경우도 미논의를 뜻하지 않는다. 본문을 읽은 14개 문서와 두 Chair Note가 이 주제의 모든 자료를 포함한다고 가정하지 않는다.

## Source — 원문으로 가는 길

아래 로컬 ZIP을 열고 표시된 member를 읽으면 본문에서 인용한 절·Proposal·Observation·표를 찾을 수 있다. 회사가 작성한 discussion 문서와 draft reply는 제출 문서로 읽는다.

<a id="s-r1-2603495"></a>
**R1-2603495 — RAN2 LS, RAN1 #125.** *LS on evaluation assumptions for contention based PUSCH transmission*. “1 Overall description”, “2 Actions”.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603495.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2603495/R1-2603495.zip). Member: `R1-2603495(R2-2602815).docx`. 본문 Source는 RAN2이며 공식 목록에는 RAN2와 OPPO가 함께 기재되어 있다.

<a id="s-r1-2603620"></a>
**R1-2603620 — vivo, #125.** *Discussion on contention based PUSCH transmission*. “DMRS”, “Scrambling ID”, “UE ID”, Observation 2, Proposal 2·3.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603620.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2603620/R1-2603620.zip). Member: `R1-2603620_Discussion on contention based PUSCH transmission.docx`.

<a id="s-r1-2603671"></a>
**R1-2603671 — Spreadtrum/UNISOC, #125.** *Draft reply LS on evaluation assumptions for contention based PUSCH transmission*. “Reply to Question”.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603671.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2603671/R1-2603671.zip). Member: `R1-2603671.docx`.

<a id="s-r1-2603673"></a>
**R1-2603673 — Ericsson, #125.** *On RAN2 LS on evaluation assumptions for contention based PUSCH transmission*. “Discussion”, Figure 1, Table 1, Observation 1·4, Proposal 2.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603673.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2603673/R1-2603673.zip). Member: `R1-2603673 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<a id="s-r1-2603806"></a>
**R1-2603806 — NEC, #125.** *Discussion on reply LS on evaluation assumptions for contention based PUSCH transmission*. “Discussion on the LS reply”, Proposal 1.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603806.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2603806/R1-2603806.zip). Member: `R1-2603806.docx`.

<a id="s-r1-2603807"></a>
**R1-2603807 — NEC 제출, #125.** *Draft reply LS on evaluation assumptions for contention based PUSCH transmission*. “1. Overall Description”.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603807.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2603807/R1-2603807.zip). Member: `R1-2603807.docx`. 문서 안의 Source `[RAN1]`은 초안 표기다.

<a id="s-r1-2603957"></a>
**R1-2603957 — Xiaomi, #125.** *Draft Reply LS on evaluation assumptions for contention based PUSCH transmission*. “1 Overall description”.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603957.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2603957/R1-2603957.zip). Member: `R1-2603957.docx`.

<a id="s-r1-2604097"></a>
**R1-2604097 — OPPO, #125.** *Discussion on LS on evaluation assumptions for contention based PUSCH transmission*. Blind decoding·detection probability 절, Observation 2·3.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604097.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2604097/R1-2604097.zip). Member: `R1-2604097/R1-2604097 Discussion on LS on evaluation assumptions for contention based PUSCH transmission-v2.docx`.

<a id="s-r1-2604147"></a>
**R1-2604147 — Samsung, #125.** *Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission*. Figures 1·2, Table 1, Observation 2–6, Proposal 1, Appendix.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604147.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2604147/R1-2604147.zip). Member: `R1-2604147 Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<a id="s-r1-2604209"></a>
**R1-2604209 — Ofinno, #125.** *Discussion on Reply LS on evaluation assumptions for contention based PUSCH transmission*. “Question 1: UE differentiation upon collision”, Case 1·2, Observation 2, Annex.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604209.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2604209/R1-2604209.zip). Member: `R1-2604209 Discussion on Reply LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<a id="s-r1-2604920"></a>
**R1-2604920 — Huawei/HiSilicon, #125.** *Discussion on RAN2 LS on evaluation assumptions for contention based PUSCH transmission*. PUSCH time domain·DMRS design 절, “Position in RAN1 to RAN2 LS”.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604920.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/125/R1-2604920/R1-2604920.zip). Member: `R1-2604920.docx`.

<a id="s-r1-2605343"></a>
**R1-2605343 — Ericsson, #126.** *On RAN2 LS on evaluation assumptions for contention based PUSCH transmission*. Figures 1–3, Table 1, Observation 5, Proposal 2·3.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Docs/R1-2605343.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/126/R1-2605343/R1-2605343.zip). Member: `R1-2605343 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<a id="s-r1-2606713"></a>
**R1-2606713 — Huawei/HiSilicon, #126.** *Draft reply LS on evaluation assumptions for contention based PUSCH transmission*. “1 Overall description”, SLS assumption table.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Docs/R1-2606713.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/126/R1-2606713/R1-2606713.zip). Member: `R1-2606713.docx`.

<a id="s-r1-2606780"></a>
**R1-2606780 — Ericsson, #126.** *On RAN2 LS on evaluation assumptions for contention based PUSCH transmission*. “Background”의 수정 설명, Figures 1–3, Table 1, Observation 5, Proposal 2·3.
[공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Docs/R1-2606780.zip) · [로컬 ZIP](../data/raw/tdocs/ran1/126/R1-2606780/R1-2606780.zip). Member: `R1-2606780 On RAN2 LS on evaluation assumptions for contention based PUSCH transmission.docx`.

<a id="s-chair-125"></a>
**RAN1 #125 Chair Note — 선택본 `eom`.** `Chair notes RAN1#125_eom.docx`, R1-2603495 항목과 “Relevant tdocs”. [원문 DOCX](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Inbox/Chair_notes/Chair%20notes%20RAN1%23125_eom.docx) · [로컬 DOCX](../data/raw/chair-notes/ran1/125/cn-fb2096be7849baa7e4dd59cd7b0b5316e7c4c2c66bfbc407ebb7f4ce25bf883b/Chair%20notes%20RAN1%23125_eom.docx)

<a id="s-chair-126"></a>
**RAN1 #126 Chair Note — 선택본 `eom1`.** `Chair notes RAN1#126_eom1.docx`, “CB-PUSCH”, R1-2605343 항목, “Other physical layer signals, channels and procedure”의 R1-2603495 주석과 LLS 표. [원문 DOCX](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Inbox/Chair_notes/Chair%20notes%20RAN1%23126_eom1.docx) · [로컬 DOCX](../data/raw/chair-notes/ran1/126/cn-c479bf236bfabef0723f0c5947841e47cd436f54379358fd9299c47c2c39702c/Chair%20notes%20RAN1%23126_eom1.docx)
