## Summary

Describe the change and why it is needed.

## Validation

- [ ] ruff check src tests tools
- [ ] python -m pytest -q
- [ ] python tools/validate_design.py --no-hashes
- [ ] python -m pip check

## Evidence impact

Choose one:

- [ ] Code/docs only; no scientific claim changes
- [ ] New prospective research work
- [ ] Additive correction/erratum to published documentation
- [ ] Other (explain below)

Explain any effect on data boundaries, frozen protocols, model selection, calibration, thresholds, or claims.

## Safety / integrity

- [ ] No raw/restricted data, secrets, weights, or machine-local receipts are added
- [ ] No safety or integrity threshold is weakened silently
- [ ] New behavior has regression coverage where applicable
