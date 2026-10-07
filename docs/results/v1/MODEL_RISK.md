# v1 Model-Risk Summary

The v1 post-hoc appendix produced a 12-item model-risk register. The most material findings are:

1. **Agent operability, critical**: 0/279 authoritative admitted Agent cases achieved executable success.
2. **Agent action safety, high**: 11 unsafe proposals and one wrong committed action were observed; host prevention is not equivalent to model safety.
3. **Confirmation power, high**: the original paired confirmation is permanently incomplete and the supplemental comparison remains underpowered.
4. **Calibration drift, high**: D1 overpredicts on final and shows a calibration slope below one; post-hoc recalibration improved descriptive late-period metrics but was not applied.
5. **Error concentration, high**: a small fraction of rows contributes a large share of total logloss.
6. **Challenger disagreement, high**: D1 and D4 diverge materially in structured hashed partner/category regimes.
7. **Parameter sensitivity, medium-high**: coefficient magnitude and neural predictions change materially across frozen regularization/learning-rate variants.
8. **Value materiality, high**: observed benchmark value is highly concentrated and binary conversion probability is not a value model.
9. **Monitoring evidence, high**: only 12 final origin-day slices are available, so reference bands are not validated production alerts.
10. **Row identity/reproducibility, medium**: non-unique ordering ties can change row-level attribution under parallel query execution; v2 should persist a globally unique row identifier.
11. **Neural superiority, medium-high**: D4 did not establish superiority over D1.
12. **Full adaptive integration, high**: v1 local Agent/numerical serving is not a frozen full-world adaptive executor.

## v2 governance implications

- audit Agent evaluator/host contracts before large model evaluation;
- use zero wrong-commit and zero unauthorized-effect readiness gates;
- freeze any recalibration, threshold, or challenger-switch rule prospectively;
- separate probability ranking from value/materiality objectives;
- require stable business semantics before acting on hashed slices;
- collect enough temporal units before enabling automated monitoring actions;
- use unique row IDs in every prediction artifact;
- use truly new eligible data for replication.
