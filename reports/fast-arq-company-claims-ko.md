# Fast-ARQ: RAN1 #125–#126의 회사별 Contribution과 회의 논의

## 핵심 요약

현재 로컬 문서에서 Fast-ARQ의 설계 질문은 세 갈래로 나타난다. UL에서는 HARQ process failure를 어떤 DCI로 알릴지가 쟁점이다. 성공한 process의 ACK까지 명시할 필요가 있는지도 별도로 논의한다. DL에서는 NACK-to-ACK 오류율 설계와 오류 검출·보고의 필요성을 다룬다. [vivo, Proposal 1–3](#source-r1-2603619), [CATT, Observation 1·Proposal 4](#source-r1-2603887), [OPPO, Proposal 1–3](#source-r1-2604096).

vivo의 문서는 UL scheduling DCI를 이용한 NACK 전달을 제안한다. OPPO의 문서는 scheduling DCI와 여러 process를 위한 dedicated DCI를 함께 고려하며, 두 방식의 적용 조건을 설명한다. ZTE·Sanechips의 문서는 특정 DCI 방식을 고르기보다 HARQ 의제에서 RAN1 측면을 계속 연구하자고 제안한다. [vivo, Proposal 1](#source-r1-2603619), [OPPO, UL discussion·Proposal 1](#source-r1-2604096), [ZTE·Sanechips, Proposal 1](#source-r1-2604801).

선택된 Chair Note에서 #125는 HARQ 연구에 포함해 결론이 나면 RAN2에 응답한다는 진행 방향을 기록한다. #126은 같은 의제의 후속 논의와 “No immediate RAN1 action”을 기록한다. 이 기록만으로 특정 회사 설계의 채택을 확인할 수는 없다. [#125 회의 논의](#source-chair125), [#126 회의 논의](#source-chair126).

## 1. 조사 범위와 배경

RAN1 #125–#126에서 기존에 찾아 둔 Fast-ARQ / Fast ARQ 문서 8개의 로컬 원문과 읽을 수 있는 본문을 확인했다. 구성은 회사 contribution 7개와 RAN2의 수신 LS 1개다. #125 회사 문서는 6개이고 #126 회사 문서는 Samsung의 1개이므로, 두 회의 전체나 모든 조직의 논의를 대표하는 자료로 해석하지 않는다. 아래 Proposal·Observation·Conclusion은 원문에 나타난 제안·관찰·결론을 구분하는 표기다.

배경 LS인 R1-2603486은 RAN2가 보낸 문서다. 이 LS는 UL에서 HARQ 재전송을 더 이상 시도하지 않지만 데이터 수신은 실패한 경우를 process failure로 설명한다. 해당 failure의 명시적 NACK indication을 받은 UE가 관련 데이터의 ARQ 재전송을 시작하도록 하는 방향을 제시하며, signaling 설계는 RAN1에 맡긴다. 메타데이터에 MediaTek도 표시되지만 원문 발신자는 RAN2이므로, 이 내용을 MediaTek 회사 제안으로 귀속하지 않는다. [RAN2, R1-2603486, “1 Overall description”](#source-r1-2603486).

## 2. 기술 질문별 Company Contribution

### 2.1 UL failure indication을 어떤 DCI로 전달할 것인가?

**vivo — R1-2603619, Proposal 1.** 특정 HARQ process failure로 더 빠른 UL ARQ를 시작하는 연구에서 명시적 NACK을 UL scheduling DCI로 전달하자고 제안한다. 문서의 예시는 해당 process의 이전 TB를 가리키는 추가 bit를 사용한다. 여러 process를 한 번에 알리는 별도 DCI도 검토하지만, 제안은 scheduling DCI 쪽이다. 핵심 원문은 “the explicit NACK indication is conveyed by a UL scheduling DCI”이다. [Discussion, Options 1–2·Proposal 1](#source-r1-2603619).

**OPPO — R1-2604096, Proposal 1과 그 앞의 분석.** UL scheduling DCI에 명시적 ACK/NACK을 넣는 Option 1과, 여러 PUSCH/HARQ process의 정보를 전달하는 dedicated DCI인 Option 2를 고려한다. 문서는 Option 1이 UL grant 발행에 종속되므로 UL 비활성 기간, 다른 carrier/cell로의 전환, configured-grant 사용 때 한계가 있다고 설명한다. 또 NR NTN의 Mode B처럼 같은 process의 첫 PUSCH를 받기 전에 연속 PUSCH를 scheduling하는 경우에는 이 방식의 ACK/NACK 표시가 유효하지 않다고 설명한다. 이어 scheduling에 독립적인 상태 관리를 위해 Option 2를 주된 기준으로 삼아야 한다고 서술한다. 다만 Proposal 1 자체는 두 방식을 “options can be considered”로 둔다. [“Discussion on UL fast ARQ”, Options 1–2·Proposal 1](#source-r1-2604096).

**CATT — R1-2603887, Proposal 1.** UL Fast-ARQ의 process 상태를 L1 DCI로 표시하자고 제안한다. 앞선 분석은 L2 MAC CE와 비교하며, DCI가 직접 실패를 알리면 RLC/MAC의 STATUS 보고 생성과 DCI–PDSCH 사이의 지연을 줄일 수 있다고 설명한다. [“UL fast ARQ”, Proposal 1과 앞 문단](#source-r1-2603887).

**Huawei·HiSilicon — R1-2604921, Conclusion.** 특정 HARQ process 또는 복수 process의 failure를 DCI의 명시적 indication으로 알려 더 빠른 UL ARQ를 촉발하는 방향을 결론으로 제시한다. 핵심 문구는 “Support explicit indication in DCI for given HARQ process(es) failure”이며, 이 Conclusion은 구체적인 DCI 형식을 하나로 지정하지 않는다. [Conclusion](#source-r1-2604921).

### 2.2 NACK만 알릴 것인가, 성공한 process의 ACK도 알릴 것인가?

**vivo — R1-2603619, Proposal 2.** 명시적 ACK의 필요성과 NACK 설계를 ACK까지 확장할 수 있는지를 추가 연구하자고 제안한다. 근거 문단은 기존 NDI toggling으로 HARQ buffer를 비울 수 있다는 점과, 같은 bit에 failure/success를 함께 표시할 때 buffer 처리의 혼동 가능성을 든다. [Discussion, Proposal 2와 앞 문단](#source-r1-2603619).

**CATT — R1-2603887, Observation 1.** NACK만 표시할지 명시적 ACK/NACK을 표시할지는 signaling 설계에 맡길 수 있다고 관찰로 제시한다. 핵심 문구는 “choose either only indicating HARQ NACK or supporting explicit ACK/NACK indication”이다. [Discussion, Observation 1](#source-r1-2603887).

**OPPO — R1-2604096, UL discussion.** 이 문서는 explicit ACK가 UE soft-buffer 관리와 DCI 누락·UL skipping의 모호성 해소에 유익하다고 설명한다. Proposal 1은 이에 따라 DCI의 explicit ACK/NACK을 제시한다. [“Discussion on UL fast ARQ”, Proposal 1 직전 문단](#source-r1-2604096).

**Samsung — R1-2604142·R1-2605792, Observation 3.** 두 문서는 HARQ buffer를 비우는 용도에서는 명시적 ACK가 기존 NR 방식보다 추가 이점을 주지 않는다고 관찰한다. 앞 문단은 같은 process에 새 TB가 사용될 때 NDI toggling으로 buffer를 비울 수 있음을 근거로 든다. “for clearing the HARQ buffer”라는 한정을 다른 모든 ACK 용도로 확대하지 않는다. [#125, §2.1 Observation 3](#source-r1-2604142), [#126, §2.1 Observation 3](#source-r1-2605792).

### 2.3 여러 process·carrier와 failure 발생 조건을 어떻게 다룰 것인가?

**CATT — R1-2603887, Proposal 2–3.** 단일 carrier와 다중 carrier 모두에서 UL HARQ process 상태 표시를 고려하자고 제안한다. Proposal 3은 ① UL grant가 가리키는 HPN의 이전 데이터 상태를 표시하는 방식, ② 하나 이상의 carrier에서 여러 process의 ACK/NACK을 bitmap으로 표시하는 방식, ③ 실패한 HPN의 개수와 각 HPN을 별도 필드로 표시하는 방식을 고려 대상으로 열거한다. 앞선 분석은 각각 scheduling 제약, bitmap overhead, ACK를 표시하지 못하는 한계를 구분한다. [“UL fast ARQ”, Proposal 2–3](#source-r1-2603887).

**Samsung — R1-2604142·R1-2605792, Observation 1–2.** 두 문서는 HARQ process failure가 “under typical conditions”에서는 드물다고 관찰한다. 또 failure 때 cross-cell ARQ 전송이 유익하다고 관찰한다. 앞 문단의 예시는 blockage 때문에 같은 cell에서의 HARQ 재전송이 제한되는 경우이며, 다른 cell의 더 나은 coverage를 ARQ에 사용할 가능성을 설명한다. [#125, §2.1 Observation 1–2](#source-r1-2604142), [#126, §2.1 Observation 1–2](#source-r1-2605792).

### 2.4 DL HARQ-ACK와 NACK-to-ACK 신뢰도는 어떻게 설계할 것인가?

**vivo — R1-2603619, Proposal 3.** HARQ-ACK feedback의 주 목적을 HARQ 동작으로 두고, 5G NR의 신뢰도 요구사항을 6GR 보고 방식의 기준선으로 재사용할 수 있다고 제안한다. DL Fast-ARQ 문제를 위한 추가 개선은 HARQ 동작용 feedback 설계와 분리해 연구할 수 있다는 조건도 함께 둔다. [Discussion, Proposal 3](#source-r1-2603619).

**OPPO — R1-2604096, Proposal 2.** 6GR HARQ-ACK feedback과 PUCCH 형식 설계에서 NACK-to-ACK 오류율을 낮게 유지하자고 제안한다. Proposal 2에 이어지는 구체 문장은 **CRC가 없는 HARQ-ACK 전송에서 0.1%를 넘지 않을 것**으로 범위를 한정한다. 이는 contribution의 설계 제안이며 모든 feedback 형식이나 최종 6G 규격에 일괄 적용되는 확정 수치가 아니다. [“Discussion on DL fast ARQ (NACK-2-ACK error)”, Proposal 2](#source-r1-2604096).

**Huawei·HiSilicon — R1-2604921, Conclusion.** 현재 설계 가정에서 NACK-to-ACK 목표 오류율이 통상 10⁻³–10⁻⁴로 이미 낮다는 전제에서, 이 문제만을 위한 명시적 방식을 추가할 동기가 약하다고 결론짓는다. 이 숫자는 문서가 둔 “under current design assumptions”의 범위에서 읽어야 한다. [Conclusion 첫 문단](#source-r1-2604921).

### 2.5 UE가 NACK-to-ACK 오류를 검출하고 보고할 필요가 있는가?

**CATT — R1-2603887, Proposal 4.** 6GR에서 L1/L2의 NACK-to-ACK 오류 검출과 해당 오류의 보고 방식을 연구하자고 제안한다. 문서는 NACK 이후 같은 HARQ process에 새 TB가 도착하는 경우 등을 검출 예시로 들며, 검출·보고가 aNB에 실패 정보를 제공해 더 이른 ARQ 시작을 돕는 방향을 설명한다. 구체 검출 방식을 이미 확정했다는 의미는 아니다. [“DL fast ARQ”, Proposal 4와 앞 문단](#source-r1-2603887).

**Samsung — R1-2604142·R1-2605792, Observation 4.** UE가 검출한 NACK-to-ACK 오류를 보고하는 것이 해당 오류에 대한 HARQ 신뢰도를 높이는 방법이라고 관찰한다. 앞 문단은 UE가 NACK을 보낸 process에 새 TB의 grant를 받는 경우를 검출 예시로 든다. [#125, “DL Fast ARQ”, Observation 4](#source-r1-2604142), [#126, 같은 절](#source-r1-2605792).

**OPPO — R1-2604096, Proposal 3.** 상세 설계 전에 UE의 NACK-to-ACK 오류 보고가 필요한지와 사용 사례부터 확인하자고 제안한다. 앞선 분석은 같은 HARQ ID가 다시 scheduling될 때까지 검출이 지연될 수 있고, 오류율 목표에 따라 보고의 이점도 달라질 수 있다고 설명한다. 따라서 “first identify the necessity and use case(s)”라는 연구 순서를 유지해 읽는다. [“Discussion on DL fast ARQ (NACK-2-ACK error)”, Proposal 3](#source-r1-2604096).

**Huawei·HiSilicon — R1-2604921, Conclusion.** 이 문서는 NACK-to-ACK 문제를 다루는 DL Fast-ARQ를 위해 추가 L1 signaling이나 절차를 표준화하지 말아야 한다고 결론으로 제시한다. 앞의 낮은 오류율 가정과 signaling 비용에 관한 설명이 이 결론의 문맥이다. [DL discussion·Conclusion](#source-r1-2604921).

### 2.6 추가 연구와 RAN2 응답 범위를 어떻게 정할 것인가?

**ZTE Corporation·Sanechips — R1-2604801, Proposal 1.** RAN2 LS에 대응해 Fast-ARQ 재전송의 RAN1 측면을 HARQ 의제에서 더 연구하는 방식을 선호한다고 제안한다. 핵심 원문은 “further study RAN1 aspects of fast ARQ retransmissions in HARQ agenda”이다. 앞 문단은 관련 결정이 내려지면 이를 RAN2에 전달할 수 있다고 설명한다. 이 자료는 구체적인 DCI 형식보다 연구 위치와 응답 순서를 다룬다. [Discussion, Proposal 1](#source-r1-2604801).

**Huawei·HiSilicon — R1-2604921, Conclusion.** 관련 설계 측면과 가정이 RAN1에서 정리될 때까지 RAN2에 대한 UL/DL Fast-ARQ 응답 LS를 미루자는 결론을 제시한다. 문서가 지적한 open issue 때문에 당시 포괄적인 답변이 어렵다는 문맥이다. [“Position from RAN1 to RAN2 LS”·Conclusion](#source-r1-2604921).

## 3. 회의에서 무엇이 논의되었는가?

### RAN1 #125 — Meeting Discussion

선택된 회의 말 Chair Note는 R1-2603486의 LS를 설명한 다음 vivo, CATT, OPPO, Samsung, ZTE·Sanechips, Huawei·HiSilicon의 관련 TDoc을 나열한다. 논의 설명은 AI 10.5.4.3의 HARQ 연구에 이 사안을 포함하고, RAN1이 결론을 내리면 응답하겠다고 기록한다. 이 목록은 해당 문서들의 논의상 연결을 보여주지만, 개별 설계의 채택 여부를 알려주지는 않는다. [Chair notes RAN1#125_eom, “R1-2603486 LS on fast ARQ” 및 “Relevant tdocs”](#source-chair125).

### RAN1 #126 — Meeting Discussion

선택된 회의 말 Chair Note의 “Fast-ARQ” 항목은 Samsung의 R1-2605792를 RAN2 LS R1-2603486의 후속 논의로 연결한다. AI 10.5.4.3에서 계속 다루고 결론이 나면 응답한다는 설명 뒤에 “No immediate RAN1 action”이 붙는다. 이를 Fast-ARQ 연구의 거절이나 종료로 해석하지 않는다. [Chair notes RAN1#126_eom1, “Fast-ARQ”](#source-chair126).

### Meeting Outcome — 확인 범위

이번 로컬 조회에는 #125·#126의 결과를 기록한 권위 있는 회의 보고서가 포함되지 않았다. 두 회의의 Fast-ARQ 기술 결정은 현재 자료로 확인하지 못했다. 따라서 위의 회의 진행 기록을 특정 signaling 방식의 Agreement나 채택으로 바꾸지 않는다. 이는 두 회의에 결정이 없었다는 뜻이 아니다.

Samsung의 두 contribution에는 “Draft reply LS”가 들어 있다. 그 안의 `<Relevant RAN1 agreement if made can be inserted here>`는 향후 agreement가 생기면 넣을 자리다. 회사 초안의 이 문구를 이미 이루어진 회의 결정으로 읽으면 안 된다. [R1-2604142, §3.1](#source-r1-2604142), [R1-2605792, §3.1](#source-r1-2605792).

## 4. Open Issue / Evidence Gap

다음 사항은 후속 자료를 읽을 때 확인할 질문이다. 이 보고서가 회사 간 합의·반대나 새로운 설계 관계를 판정한 결과는 아니다.

- Scheduling DCI에 연결된 indication이 UL 비활성·configured grant·carrier 전환에서 충분한지, 별도 DCI를 어떤 범위에서 쓸지 확인해야 한다. OPPO의 적용 조건과 CATT의 세 가지 표시 방식을 함께 읽으면 이 질문의 범위가 드러난다. [OPPO, UL discussion](#source-r1-2604096), [CATT, Proposal 3](#source-r1-2603887).

- NACK-to-ACK 보고의 필요성을 판단하려면 목표 오류율, 검출까지의 지연, 보고 비용을 같은 조건에서 살펴야 한다. 여기서는 회사 문서들의 설계 주장과 관찰을 읽었으며, 공통 조건의 성능 비교를 수행하지 않았다. [OPPO, DL discussion·Proposal 3](#source-r1-2604096), [Huawei·HiSilicon, DL discussion](#source-r1-2604921).

- 선택된 Chair Note에 없는 문서는 논의되지 않았다고 단정할 수 없다. 회의 말 파일인 `eom`·`eom1`도 그 이름만으로 최종본이라고 보장되지 않는다. #125·#126의 확인 가능한 공식 회의 결과 자료가 보강되면 Meeting Outcome을 다시 확인할 수 있다.

- OPPO Proposal 2의 상세 문장은 본문에서 “HARQ-ACK transmission without CRC”, Conclusion 반복 부분에서는 “UL HARQ-ACK transmission without CRC”로 적혀 있다. §2.4는 DL discussion 본문의 Proposal 2를 출처로 삼았다. [OPPO, Proposal 2의 본문과 Conclusion 반복](#source-r1-2604096).

## 5. Sources — 원문 찾기

기술 문장을 직접 확인하려면 로컬 ZIP을 열고 표의 DOCX member를 읽으면 된다. 본문의 절 이름이나 Proposal·Observation 번호를 검색하면 해당 문맥에 도달할 수 있다. 표의 제목은 저장된 공식 목록 기준이다. 공식 링크는 이미 저장된 주소이며, 이 보고서를 위해 추가 자료를 내려받지 않았다.

| Source | 조직 / 회의 | 제목 · ZIP 안의 원문 | 바로 찾을 위치 |
| --- | --- | --- | --- |
| <a id="source-r1-2603486"></a>**R1-2603486** · [로컬 ZIP](/home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603486/R1-2603486.zip) · [공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603486.zip) | RAN2, MediaTek / RAN1 #125 | LS on fast ARQ<br>`R1-2603486(R2-2602813).docx` | 1 Overall description; 2 Actions |
| <a id="source-r1-2603619"></a>**R1-2603619** · [로컬 ZIP](/home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603619/R1-2603619.zip) · [공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603619.zip) | vivo / RAN1 #125 | Discussion on fast ARQ<br>`R1-2603619 Discussion on fast ARQ.docx` | Discussion, Proposal 1–3 |
| <a id="source-r1-2603887"></a>**R1-2603887** · [로컬 ZIP](/home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2603887/R1-2603887.zip) · [공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2603887.zip) | CATT / RAN1 #125 | Discussion on fast ARQ for 6G<br>`R1-2603887.docx` | UL fast ARQ, Observation 1·Proposal 1–3; DL fast ARQ, Proposal 4 |
| <a id="source-r1-2604096"></a>**R1-2604096** · [로컬 ZIP](/home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604096/R1-2604096.zip) · [공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604096.zip) | OPPO / RAN1 #125 | Discussion on fast ARQ LS from RAN2<br>`R1-2604096 OPPO Discussion on fast ARQ LS.docx` | Discussion on UL fast ARQ, Proposal 1; Discussion on DL fast ARQ, Proposal 2–3 |
| <a id="source-r1-2604142"></a>**R1-2604142** · [로컬 ZIP](/home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604142/R1-2604142.zip) · [공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604142.zip) | Samsung / RAN1 #125 | Discussion on LS on Fast ARQ<br>`R1-2604142 Reply LS on Fast ARQ.DOCX` | 2.1 UL Fast ARQ, Observation 1–3; DL Fast ARQ, Observation 4; Draft reply LS |
| <a id="source-r1-2604801"></a>**R1-2604801** · [로컬 ZIP](/home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604801/R1-2604801.zip) · [공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604801.zip) | ZTE Corporation, Sanechips / RAN1 #125 | Discussion on RAN2 LS on fast ARQ<br>`R1-2604801 Discussion on RAN2 LS on fast ARQ.docx` | Discussion, Proposal 1 |
| <a id="source-r1-2604921"></a>**R1-2604921** · [로컬 ZIP](/home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/125/R1-2604921/R1-2604921.zip) · [공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Docs/R1-2604921.zip) | Huawei, HiSilicon / RAN1 #125 | Discussion on the LS from RAN2 on fast ARQ<br>`R1-2604921.docx` | Discussion on uplink/downlink Fast ARQ; Conclusion |
| <a id="source-r1-2605792"></a>**R1-2605792** · [로컬 ZIP](/home/jjuns/3gpp-study-engine/data/raw/tdocs/ran1/126/R1-2605792/R1-2605792.zip) · [공식 ZIP](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Docs/R1-2605792.zip) | Samsung / RAN1 #126 | Draft reply LS on Fast ARQ<br>`R1-2605792 Reply LS on Fast ARQ Final.docx` | 2.1 UL Fast ARQ, Observation 1–3; DL Fast ARQ, Observation 4; Draft reply LS |

R1-2603486의 조직 칸은 메타데이터를 그대로 표시한 것이다. 문서 본문의 발신자는 RAN2이다. R1-2605792는 공식 목록의 제목이 “Draft reply LS on Fast ARQ”이고, 원문 표제는 “Discussion on LS on Fast ARQ”이다.

| Meeting Discussion Source | 로컬 원문 / 기존 공식 주소 | 바로 찾을 위치 |
| --- | --- | --- |
| <a id="source-chair125"></a>RAN1 #125 · `Chair notes RAN1#125_eom.docx` | [로컬 DOCX](/home/jjuns/3gpp-study-engine/data/raw/chair-notes/ran1/125/cn-fb2096be7849baa7e4dd59cd7b0b5316e7c4c2c66bfbc407ebb7f4ce25bf883b/Chair%20notes%20RAN1%23125_eom.docx) · [공식 DOCX](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_125/Inbox/Chair_notes/Chair%20notes%20RAN1%23125_eom.docx) | R1-2603486 LS on fast ARQ; Relevant tdocs |
| <a id="source-chair126"></a>RAN1 #126 · `Chair notes RAN1#126_eom1.docx` | [로컬 DOCX](/home/jjuns/3gpp-study-engine/data/raw/chair-notes/ran1/126/cn-c479bf236bfabef0723f0c5947841e47cd436f54379358fd9299c47c2c39702c/Chair%20notes%20RAN1%23126_eom1.docx) · [공식 DOCX](https://www.3gpp.org/ftp/tsg_ran/WG1_RL1/TSGR1_126/Inbox/Chair_notes/Chair%20notes%20RAN1%23126_eom1.docx) | Fast-ARQ; R1-2605792 |
