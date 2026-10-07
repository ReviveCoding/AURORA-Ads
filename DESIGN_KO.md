# AURORA-Ads v2.0 최종 end-to-end 설계

**상태: 구현 착수용 설계 확정. 모델 학습·실험 결과 없음.**

이 프로젝트는 지연 전환, 예산, 분포 변화가 있는 광고 의사결정을 수치 모델로 평가하고,
단일 LLM agent가 같은 정책을 정확하게 호출·실행·설명하는지를 검증한다.
ToT, multi-agent, 영상 추천, 실제 광고비 집행, paid cloud는 범위에 없다.

## 1. 연구 목표

세 가지 결과를 별도로 낸다.
1. MSCP가 강한 기존 정책보다 완료된 episode 가치가 높은가?
2. single agent 학습이 실제 과업·도구 실행을 개선하는가?
3. 해당 로컬 workload를 안정적이고 재현 가능하게 실행하는가?

서로 다른 결과를 하나의 AURORA 종합점수로 합치지 않는다. baseline 유지도 유효한 결론이다.
MSCP는 Maturity- and Support-Aware Constrained Policy이며 새 regret theorem을 주장하지 않는다.

## 2. 증거 영역과 데이터

| 영역 | 자료 | 주 사용 | 금지되는 해석 |
|---|---|---|---|
| R1 | Criteo Attribution | CTR, 시간 패턴, descriptive attribution | 실제 원금액 ROAS, randomized causal lift |
| R2 | Criteo Uplift v2.1 | released-population assignment ITT, targeting | 개별 CATE 정답, pacing/bid action 효과 |
| R3 | Sponsored Search Conversion | post-click 전환·지연·attributed value | impression CTR, raw creative semantics |
| R4 | OBD men | propensity 있는 position-conditional OPE | 임의 target에 BTS 평균을 정답으로 사용 |
| R5 | iPinYou optional | 조건부 historical auction replay | 보지 못한 auction의 실제 counterfactual 정답 |
| S1 | 명시적 synthetic worlds | 전체 정책·예산·반사실 실험 | real customer/production 효과 |
| A1 | 실행 가능한 agent tasks | 도구·행동·수치·근거 평가 | 사람 평가 완료, production safety certification |

데이터 출처 간 사용자/캠페인 ID를 join하지 않는다. 한 source CTR과 다른 source CVR의 곱을
검증된 impression value라고 부르지 않는다. 해시·버전·라이선스·이전 노출 여부를 기록한다.
기존에 본 공개 benchmark의 새 hash split은 새로운 외부 test가 아니다.

데이터 획득은 cache-first이다. downloader 기본값은 offline plan이고, 사용자 license acknowledgment와
명시적 --apply가 있어야 네트워크를 사용한다. HTTP 완료와 schema/CRC/시간 admission은 다르다.

## 3. Desktop study, EDA, 전처리

문헌 matrix는 방법의 목적, 식별 가정, 필요한 필드, nearest baseline, 계산량을 기록한다.
EDA는 누락/중복/성숙도/희소 category/캠페인 및 시간 drift/propensity support를 본다.
원자료는 bounded streaming으로 Parquet/DuckDB에 저장하고 malformed rows는 이유와 함께 격리한다.
origin_time, information_time, outcome_time, received_at을 분리한다.

R3의 실제 reporting-arrival clock은 공개되지 않는다. 주 분석의 received_at은 click+conversion_delay
가정이며, reporting lag 추가는 synthetic sensitivity다. source timestamp 단위는 README로 확인한다.

### R3 주 분석: 7일 outcome

모든 구간은 반개방 [start,end)이다.
- M41: day41 시점에 이용 가능한 origin [0,41) 학습.
- mature-only는 origin+7<=41인 관측만 사용; delay-aware는 아직 검열된 최근 행도 likelihood에 사용.
- C54: M41이 예측한 origin [41,47)의 결과가 day54까지 성숙한 후 calibration.
- selection: origin [54,60), 결과 day67까지 관측.
- day70: M41+C54와 모든 설정 고정. primary model 재학습 없음.
- final: origin [70,82), day89까지 성숙 결과 평가.

새 모델을 학습한다면 새로운 calibration pair가 필요한 별도 secondary study다.

## 4. 모델링

예측: prior, hashed logistic/FTRL, XGBoost CUDA, embedding MLP, DCNv2.
지연: biased pending-negative 진단, mature-only, feedback correction, truncated exponential incidence,
neural finite-horizon distribution. 가치: positive-value mean, corrected log two-part, direct Tweedie/MLP.
인과: response targeting, T-learner, cross-fitted DR, 선택적 treatment-head network.

예측 주 지표는 log loss. Brier, PR-AUC, AUROC, calibration, tail/slice는 보조다.
Test ECE로 calibration 방법을 선택하지 않는다. 모든 모델은 동일 feature availability를 사용한다.

지연 likelihood는 q=P(C by H), sum f_k=1로 두고, 관측 전환은 q*f_k, 아직 관측 안 된 경우는
1-q*F(u)이다. exponential baseline도 H로 조건화하여 F(H)=1이 되게 한다.
한 origin의 여러 age snapshot을 독립 행으로 중복 누적하지 않는다.

## 5. Simulator와 정책

기본 world는 공통 shock을 갖는 8개의 비경쟁 캠페인, 서로 다른 고정 예산으로 구성한다.
14일 의사결정 뒤 7일 conversion flush를 거친다. 각 정책은 독립 state와 같은 외생 난수를 사용한다.
무이질성, zero/negative effect, nonlinear effect, fatigue/carryover, reporting/competition shift를 포함한다.
후보 모델은 latent truth, future outcome, fault ID를 보지 못한다.

Fast bidder는 fixed bid, calibrated-value bid, grid utility optimizer를 비교한다.
Slow action은 NO_CHANGE, BID_UP/DOWN, PACE_UP/DOWN, PAUSE_SEGMENT이며 15분 뒤 만료된다.
입찰 multiplier는 [0.5,1.5], 단계 10%; pace는 [0,1], 단계 0.1. 전체 예산은 늘어나지 않는다.

MSCP score:
`gross_value - (1 + scarcity_dual)*spend - operating_cost - beta*uncertainty`

실제 지출은 한 번만 계산한다. uncertainty는 실험적으로 평가한 proxy이며 안전 보장이 아니다.
Support 부족, stale state, 불가능한 action은 qualified baseline으로 돌아간다.
주 action-value update는 완전히 성숙한 origin-interval cohort reward만 사용하고 nowcast는 상태·가치·pacing 판단에 사용한다.
Pseudo reward posterior update는 별도 sensitivity다.

강한 baseline은 best safe static, rules/PID, epsilon-greedy, LinUCB, neural-linear TS,
delay-aware TS+primal-dual, generic-support-gated conventional, MPC이다.
MSCP에만 기계적 예산·권한 guard를 제공하지 않는다.

## 6. 측정과 식별

R2의 binary assignment는 S1의 다중 action 효과가 아니다.
S1 multi-action value 모델은 randomized S1 자료로 학습한다.
OPE용 logger는 명시적인 categorical mixture이며 guard 이후 최종 실행 action 확률을 저장한다.
TS Monte Carlo frequency를 exact logged propensity라고 기록하지 않는다.

One-step DM/IPS/SNIPS/DR는 fixed policy와 support가 있는 조건에서 비교한다.
Whole adaptive budget episode는 독립 world 완료 결과로 평가한다.
OBD는 uniform target identity control부터 수행하고, exact target reconstruction이 불가능한 BTS 비교는 diagnostic이다.

정책 primary utility:
`(unique_purchase_value - paired_no_ad_purchase_value - spend - operating_cost) / initial_budget`

MSCP와 conventional의 차이에서 동일 no-ad 항은 상쇄된다. learner는 이 oracle을 보지 않는다.
낮은 지출 자체나 duplicate conversion이 성과 개선으로 잘못 계산되지 않도록 별도 ledger를 검증한다.

## 7. 단일 agent와 학습

Fast path에 LLM을 넣지 않는다. Single agent는 다음 도구를 호출한다.
get_campaign_snapshot, query_metrics, estimate_outcomes, simulate_policy, recommend_action,
validate_action, prepare_action, commit_mock_action, build_measurement_report.

Query는 allowlist parameterized SQL. Prepare는 tenant, state version, payload, 만료, evidence를 묶는다.
Commit은 host-issued 승인 또는 명시적 MOCK_ONLY preauthorization이 필요하다.
모델이 출력한 approved=true는 승인 증거가 아니다.

Prompt-only -> SFT -> 같은 SFT에서 DPO/IPO 비교. GRPO는 선택적 bounded extension이다.
개발 Qwen3-1.7B, qualification 후 final 4B. 정확한 model/tokenizer/chat template revision을 고정한다.
초기 계획은 SFT 8천, preference 2천, final 400 task/80 family이다. 수집 완료 수치가 아니다.

Assistant와 tool arguments만 loss 대상으로 하고 tool observations/system은 mask한다.
1,024 token에 계약이 안 들어가면 tool subset 또는 사전 context 확대를 사용하며 silent truncation을 하지 않는다.
Harmful proposal, guard에 차단된 오류, committed violation, task success, over-refusal을 분리한다.

통합은 numerical policy(conventional/MSCP) x agent(prompt/learned)의 2x2다.
순수 정책 비교에는 deterministic executor를 사용한다.

## 8. 실험 진행

27개 machine-readable DAG node는 E00-E16의 세부 단계를 구현한다.
핵심 순서는 inventory -> data/EDA -> baseline/delay/causal/OPE -> simulator -> incidents/policy ->
tools/agent learning -> integration/ablation -> 각 track freeze -> 각 track confirmation -> report다.

R1/R3/Policy/Agent freeze를 분리한다. iPinYou와 GRPO 누락은 다른 core 실험을 막지 않는다.
한 source admission 실패는 해당 source 증거만 막는다. 마지막 보고서는 all-pass가 아니라
모든 track의 실제 terminal 상태가 나왔을 때 생성한다.

## 9. 통계와 결과 분석

주 정책 대조: 가장 강한 validation-selected conventional vs MSCP.
실용적 margin은 초기 예산의 1%에 해당하는 normalized utility 0.01이다.
Lower 95% CI가 0.01을 넘을 때만 실용적 우월성으로 해석한다. 이는 예상 결과가 아니다.
20개 pilot world 뒤 40-200 final world에서 .01 null margin과 .02 planning alternative를 구분할
power를 계산한다. 부족하면 UNDERPOWERED로 보고한다.

Agent는 family-macro success와 family-cluster inference, 실제 training seed variability를 보고한다.
Zero harmful observations를 zero-risk로 바꾸지 않는다. Family-any-harm의 보수적 상한은 별도 단위다.
Secondary는 Holm 또는 exploratory로 표시한다. Policy마다 같은 sampled worlds로 paired 비교한다.

후처리는 전체 평균, 지연·예산·support·shift별 slice, 오류 전이, ablation, 가치-위험 tradeoff,
학습/추론 비용, serving latency를 분석한다. 표와 수치는 frozen JSON/Parquet에서 자동 생성한다.

## 10. 엔지니어링과 자원

Windows canonical repo, WSL ext4 runtime. 두 editable clone을 만들지 않는다.
GPU heavy job은 1개. Batch/vectorized numerical compute를 병렬화한다.
CPU worker 2로 시작해 qualification 후 4까지, planned VRAM <=12GiB 및 >=2GiB headroom.
통계·추정량은 CPU FP64 참조와 비교한다. Single-GPU를 multi-GPU scaling이라고 부르지 않는다.

Fast path 프로젝트 목표는 100RPS, p95<=50ms, error<=0.1%다. Amazon SLO가 아니다.
Inference-only/feature-to-decision/HTTP/agent completion을 각각 측정한다.
Load는 open-loop arrival로 생성하고 timeout/rejection을 통계에서 지우지 않는다.
Idempotency, budget reserve/settle, stale commit, cancellation/restart/queue full/OOM/shutdown을 테스트한다.

현 PC에서 PS7.6.6, Codex0.155.1, Ubuntu22.04 WSL2, GPU16376MiB가 읽기 전용으로 관측됐다.
GPU 안정성 검증은 하지 않았다. 고부하 전에 단계별 qualification이 필요하다.
Driver/BIOS/power/global environment는 자동 변경하지 않는다.

## 11. 완료 기준

DESIGN_READY: 설계·계약·준비 코드가 일치한다.
ENGINEERING_EXECUTED: 실제 모델/서비스 코드와 smoke가 실행되었다.
CORE_TRACKS_CLOSED: 모든 core track이 유효/실패/blocked 등 실제 terminal 상태와 보고서를 갖췄다.
CORE_EMPIRICAL_COMPLETE: 모든 필수 empirical capability가 실제 유효하게 실행됐다.
SCIENTIFIC_SUPPORTED: 특정 hypothesis가 사전 기준을 통과했다.

현재 패키지는 첫 단계까지만 해당한다. 모델 우월성이나 production 효과는 아직 없다.

## 12. 실행 준비와 Codex

Prepare-Aurora.ps1은 ZIP/파일 해시, archive path, 기존 폴더 충돌, Codex flag, WSL을 확인한다.
새 repo를 만들고 project-scoped runtime만 준비한다. StartCodex 옵션은 prompt 없이
native interactive Codex를 --approve-for-me로 실행한다.

자동승인은 reviewer로 경로를 바꾸는 것이지 sandbox를 없애는 기능이 아니다.
Login/trust/managed policy/승인 거절은 여전히 사용자 조작이 필요할 수 있다.
프롬프트 없이 실행하므로 실제 구현·설치·데이터 획득·실험을 시작하지 않는다.
별도 최종 구현 프롬프트는 이 패키지에 포함하지 않았다.

7일 outcome을 쓰면서 의사결정도7일에 끝내면 자기 정책에서 나온 성숙 feedback을 거의 학습하지 못한다. 따라서 주 episode를14일로 늘렸으며, action reward는 해당15분 구간에 시작한 opportunity의 outcome만 합산한다. 겹치는7일 전체 구매를 매 action에 중복 귀속하지 않는다.
