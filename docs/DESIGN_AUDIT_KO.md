# AURORA-Ads v1 재검토와 v2 보완 기록

작성일: 2026-09-30. 이 문서는 설계 검토 기록이며 모델 성능 결과가 아니다.
기준: 기존 DESIGN_KO.md와 IMPLEMENTATION_SPEC.md 전체, 기존 acquisition/runtime 코드,
공식 데이터·Codex·학습 라이브러리 문서, 사용자 PC의 읽기 전용 설치 현황.

## 1. 결론

v1의 중심 구조는 유지한다. 한 프로젝트, 한 LLM agent, 수치 정책과 도구 실행의 분리,
실제 공개자료와 synthetic intervention의 분리, 강한 baseline, 지연 전환, GPU 제한을 유지한다.
다만 v1은 몇 가지 핵심 선택을 구현자가 임의 해석할 수 있었다. v2는 이를 구체적 실행 계약으로 바꾼다.
`docs/FINAL_SPEC.md`와 `config/*.json`이 현재 기준이고, 보존된 v1은 역사 자료다.

## 2. 주요 보완표

| 문제 | v1에 남은 위험 | v2 결정 |
|---|---|---|
| 예측 모델과 calibrator | M41 기반 calibration 후 M70 재학습으로 오해 가능 | 주 분석은 M41+C54 한 쌍 고정, day70 refit 금지 |
| 전환 시점/보고 시점 | conversion delay를 실제 수집 지연처럼 해석 가능 | received_at 가정 명시, reporting lag는 별도 synthetic sensitivity |
| 7일 전환 정의 | exponential tail과 finite-horizon incidence가 불일치 가능 | horizon-conditioned exponential CDF, F(H)=1 검증 |
| 학습 horizon | 7일 outcome과7일 episode가 같아 자기 정책의 성숙 feedback이 거의 없음 | 14일 decision+7일 flush, 완전히 성숙한 origin-interval cohort update |
| reward 중복 | pending estimate와 실제 전환의 이중 기여 위험 | primary learner는 실제 관측 reward만 업데이트 |
| reward 자기강화 | own nowcast를 정답으로 학습하여 자신감 증폭 | nowcast는 상태/가치 추정에 사용, pseudo-update는 별도 실험 |
| 비용 계산 | scarcity penalty만으로 실제 지출 누락 가능 | gross-(1+lambda)*spend-operating_cost-beta*uncertainty |
| 정책 실용성 기준 | baseline 부호에 따라 relative/absolute 기준 변경 | 0.01 normalized utility를 사전 고정 |
| pause action | resume action 없는 영구 정지 상태 가능 | action 유효기간 1개 15분 interval, 종료 후 기본값 복귀 |
| propensity | guard 전 제안 확률만 저장할 위험 | 최종 실행 action 확률로 질량 합산 |
| TS 확률 | Monte Carlo frequency를 정확한 logging propensity처럼 표현 | OPE logger는 명시적 epsilon categorical mixture |
| causal action | binary uplift를 다중 bid/pacing 효과로 재사용 가능 | binary R2와 randomized multi-action S1 분리 |
| stateful policy | one-step DR로 전체 예산 trajectory 평가할 위험 | 독립 world의 전체 성숙 결과가 주 정책 endpoint |
| organic 구매 | impression credit과 unique purchase 이중계산 | unique synthetic user-event ledger, no-ad 비교 분리 |
| OBD 비교 | BTS 평균을 임의 target policy의 정답으로 사용 | uniform identity control, exact BTS reconstruction 없으면 diagnostic |
| agent 성능 | host guard가 오류를 막아도 model이 안전하다고 오해 | harmful proposal/prevented violation/committed violation 각각 보고 |
| SFT loss | tool 결과 자체를 예측하게 학습할 위험 | assistant/tool-argument만 loss, system/tool observation mask |
| context 길이 | 1,024 token에 tools가 안 들어가 잘린 계약으로 학습 | tokenizer audit, tool subset 또는 사전 context 확대, silent truncation 금지 |
| agent 데이터 | task paraphrase/반사실 변형이 train-test를 넘나듦 | semantic family·template·schema grouping |
| 학습법 비교 | DPO/IPO의 reference·pairs·budget이 다름 | 동일 SFT/reference/pairs, 실제 objective와 token cost 기록 |
| 단일 GPU | 여러 trainer 동시실행을 병렬 계산으로 오인 | 1 heavy GPU lease, batch/vectorization으로 수치 병렬화 |
| Windows/WSL 저장소 | 서로 다른 editable Git clone으로 drift 가능 | Windows canonical source, WSL ext4 runtime만 분리 |
| 실험 의존성 | optional iPinYou/GRPO가 core completion 차단 | optional은 core freeze ancestor에서 제외 |
| 독립 확증 | agent 실패가 real-data/policy 평가까지 막음 | POLICY/AGENT/R1/R3 각각 freeze와 confirmation |
| 완료 표시 | blocked 결과가 있어도 모든 evidence complete로 오인 | TRACKS_CLOSED와 EMPIRICAL_COMPLETE 분리 |
| 재현 테스트 | CPU helper 통과를 실제 GPU 학습 검증처럼 해석 | helper/PS syntax/network/GPU/실험 상태 개별 기록 |
| 데이터 다운로드 | EOF·Range·path·실패 byte quota 미검증 | portable path, symlink, Content-Range, EOF, quota, lock 보강 |
| 승인 옵션 | never/full-access로 자동승인을 대체할 위험 | 설치된 --approve-for-me 직접 사용, sandbox 유지 |

## 3. 설계 변경의 중요한 의미

v2는 더 많은 기능을 추가하는 개정이 아니다. 가장 중요한 변화는 잘못된 비교가 좋은 결과처럼
보이지 않도록 비교 대상, 시간, 단위, action, reward, 통계 단위를 고정한 것이다.

주 정책 실험에서 LLM은 제외하고 deterministic executor를 쓴다. 통합 실험은 별도의 2x2로
수치 정책과 agent의 기여를 분리한다. 수치 정책의 이득을 자연어 표현의 개선으로 대체하지 않는다.

모든 정책에 같은 예산과 기계적 guards를 부여한다. MSCP-specific uncertainty/support 처리는
동일한 단순 support gate를 가진 강한 conventional policy와도 비교한다.

## 4. 여전히 런타임에서 확인해야 하는 것

- 원자료 실제 payload와 README/schema, 시간 단위, 중복 및 horizon coverage.
- 저작권/이용 조건의 실제 사용자 확인과 source-derived artifact의 공개 가능 범위.
- GPU 안정성 및 Python/PyTorch/TRL/PEFT/XGBoost 호환 조합.
- task schema가 context에 들어가는지, reward가 실제 정답을 평가하는지.
- pilot 분산으로 가능한 표본 수와 power. 계획된 400 task/80 family는 측정 완료 수치가 아니다.

이 조건들은 설계에서 숨긴 구멍이 아니라 명시적 admission/qualification 단계다.
조건이 실패하면 해당 증거를 BLOCKED/INVALID/UNDERPOWERED로 남기고 독립 경로는 계속한다.
실패한 요구를 synthetic data로 조용히 대체해 완료했다고 보고하지 않는다.
