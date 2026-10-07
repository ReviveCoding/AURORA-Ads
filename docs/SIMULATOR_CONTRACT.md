# S1 simulator implementation contract

Status: declared synthetic design, not observed advertising behavior or completed simulator execution.
This closes implementation choices left abstract in the overview. Data-derived anchors may be added only as a
separately versioned development configuration. They cannot silently replace this transparent reference DGP.

## Population and clocks

A world is one account with eight noncompeting campaigns and separate budgets. Fourteen decision days have
1344 controller intervals, each15minutes. Conditional on declared campaign/time shock, opportunities per interval
are Poisson with nominal mean32 per campaign. Each opportunity has one unique purchase-occasion ID. No campaign
competes for the same occasion in the primary experiment. Shared shocks make the world the independent unit.
The initial budget is selected before generating realized future traffic. Observe every policy through a7day
maturation flush after decisions end. Additional reporting lag has its own declared receipt flush.

Numeric context x has six dimensions: four bounded continuous variables, one five-level segment and one
periodic time feature. Default x1-x4 are Uniform[-1,1]; segment probabilities are uniform; the time feature is
sin(2*pi*day_fraction). Context/shock random keys are shared across arms. Campaign parameters are drawn once
from fixed development/final distributions and are never exposed as labels to the learner.

## Purchases, exposure and clicks

Organic purchase probability on an eligible occasion:
`p0 = sigmoid(-5.3 + 0.4*x1 - 0.3*x2 + 0.2*time_feature + organic_shock)`.
The final publisher-independent constants are frozen before final worlds; a sensitivity varies the intercept,
not an outcome-dependent rescaling to make the candidate win.

A win E in{0,1} produces advertised purchase probability:
`pE = sigmoid(logit(p0) + E*delta(x, campaign, time, fatigue))`.
Use the same occasion-level Uniform(0,1) draw for purchase under no-ad and advertising potential states.
One occasion contributes at most one purchase to Y in each world/arm. It may convert organically without
exposure; it is not added again as a separate ad credit. Negative delta can prevent an otherwise organic purchase.
This monotone coupling for a fixed signed delta is a variance-reduction assumption, not measured individual truth.

Clicks are a separate post-exposure observation:
`click = E * Bernoulli(sigmoid(-3.2 + 0.6*x1 + 0.2*x3 + click_shock))`.
View-through conversions are therefore possible. Do not multiply this click probability by a CVR trained on R3
and call the result S1 truth. The policy may learn S1 response/value from S1 only; R3 remains a separate study.
Positive purchase value defaults to LogNormal(log(200),0.4), in the same synthetic cost units as auction spend.
Heavy-tail/OOD alternatives are predeclared separately. Value generators do not use the proposed method's score.

## Four in-mixture mechanism families

- Weak/no heterogeneity: delta is campaign-constant, sampled from {-0.25,0,0.25}; include pure zero-effect reference worlds.
- Nonlinear heterogeneous: `delta=0.6*tanh(2*x1*x2) + 0.35*x3 + segment_offset`, segment offsets in[-0.2,0.2].
- Fatigue/carryover: `delta=0.5+0.3*x1-0.8*fatigue`; fatigue evolves by `F_next=0.8*F+0.2*win_fraction`, with F in[0,1].
- Reporting/competition shift: use the nonlinear delta, introduce a fixed-time competition step and a temporary reporting-delay shift.

Default family mixture is25% each. Parameter variation, shock amplitude and change-time ranges are recorded
before final. No-effect and negative-effect regimes are retained even if NO_BID wins. OOD mechanisms include
nonlinear feature changes not present in training, stronger fatigue, outcome-dependent permanent reporting loss,
new campaign supports and supply/eligibility collapse. OOD is separately labeled, not pooled opportunistically
into the primary mixture. The local reference and at least one misspecified generator must both be tested.

## Auction and costs

Each opportunity has an exogenous market threshold
`M = exp(0.25*x2 + market_shock + 0.4*z)`, z standard normal, median base threshold1 synthetic unit.
Payment mode is fixed per experiment. Second price: win if bid>=M, pay M. First price: win if bid>=M, pay bid.
Tie rule uses the same convention for all policies. Fixed bid/no-bid, calibrated linear bid and finite-grid
utility optimization use candidate bids [0,0.25,0.5,0.75,1,1.5,2,3], then the slow multiplier.
Bids and settlement values are quantized conservatively to1/10000 cost unit for budget accounting.
Reserve maximum payable bid atomically, settle actual payment, then release the unused reservation.
No negative balance or extra budget may be created by simultaneous requests, rounding or retries.

Controller decisions change next-interval multiplier/admission and expire after that interval. Default admission
is0.6; +/-0.1 pace actions remain in[0,1]. PAUSE sets admission to0 for one interval. NO_CHANGE applies the
preselected default. Frequency/cooldown masks and operating action costs are identical across comparison arms.
Default non-NO_CHANGE action overhead is0.01 cost unit per campaign interval, with a separate zero-cost sensitivity.
Learning algorithms cannot access the market threshold before bidding. Simulator/evaluator may retain it privately.

## Delay and available reward

For a purchase by H=7days, use a horizon-conditioned exponential delay. The default rate is2/day in fast-feedback
regimes and1/3 per day in slow regimes; contextual rates vary via a bounded log link. For each purchase draw its
delay using the conditional CDF, so D<=H by construction. This deliberately finite target is not lifetime sales.
Source-conditioned temporal data experiments use their own admitted distributions instead of this synthetic claim.

Receipt time is outcome time in the nominal environment; temporary reporting lag is added explicitly for shift
experiments. Permanent missingness is a separate partially observed environment: the evaluator retains latent
purchase truth, the policy does not. Report recorded-reward and full synthetic truth separately. No unbiasedness
claim is available for arbitrary MNAR loss.

Primary learner contributions are observed positive value or a completed zero label only. Record `pending`,
`event_observed`, `horizon_complete`, and `receipt_available` separately. A delay nowcast can affect state and pacing,
but it cannot be inserted as a newly observed reward. A later purchase does not create two reward observations.

## Calibration, learning and fair information

Warm-start action-value models use separately generated randomized controller data, not final-world oracle rewards.
Log an exact epsilon-mixture action distribution with epsilon0.1 over the eligible proposal set, and map mass to
final executed actions after all deterministic guards. Learning support, posterior state and nuisance training have
separate artifacts. The primary bandit controller approximates a stateful problem; it does not get a regret theorem
from the stateless LinUCB model. Whole-world prospective simulation is the primary evaluation.

All policies see the same allowed observation channels. Removing MSCP support/uncertainty components is an ablation;
removing shared budget/authorization guards is not a valid head-to-head comparison. Both equal-initialization and
end-to-end selected-system comparisons are reported separately where nuisance models differ.

## Required simulator qualification

- CPU tiny-world reference checks counts, clocks, costs, quantization and outcome uniqueness.
- Counter-based RNG proves policy call order does not change future exogenous channels.
- No-ad and same-policy paired differences satisfy algebraic/null controls.
- Finite-horizon delay CDF mass and treatment-effect sign are tested.
- Latent truth, generator IDs and fault IDs cannot appear in model/agent observation schemas.
- Budget constraints agree for sequential and vectorized execution.
- Statistical Monte Carlo checks of known effects and CI coverage precede final use.
- Report per-family results, value scale sensitivity and simulator-form limitations.

These constants are a transparent implementable reference, not a validated digital twin of Amazon or Criteo.

Policy feedback uses the matured origin-interval cohort rule in FINAL_SPEC.md. The main14day decision horizon allows self-generated7day outcomes to mature before decisions end; partial positives are not complete cohort rewards.

Implementation closure (S1_BLOCKS_V1, before policy training/final outcomes):
`config/simulator_blocks.json` fixes a publisher-independent finite catalog of whole campaign parameter blocks,
partitioned among training, validation, calibration, pilot and final. The organic campaign shock is bounded
[-0.03,0.03]; it is one declared component of organic_shock. Reference coefficients and value scale remain
unchanged. Entire joint parameter vectors, not merely random seeds, are withheld. Separate OOD runs hold out
nonlinear feature changes, stronger fatigue, value-dependent permanent receipt loss, supply collapse and an
additive misspecified generator. OOD outcomes never select a primary final-world mixture or model.
