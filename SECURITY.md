# Security policy

AURORA-Ads is a research repository that includes local agent/tool orchestration, authorization boundaries, state transitions, and resource-control code. Security reports are welcome when they concern the published code or repository configuration.

## Reporting a vulnerability

Please use **GitHub private vulnerability reporting** for security-sensitive findings. Do not open a public issue containing exploit details, credentials, private data, or secrets.

Include, when possible:

- affected commit or release,
- affected file/component,
- reproduction steps,
- expected security boundary,
- observed behavior and impact,
- suggested mitigation if known.

## Scope

Relevant examples include:

- authorization or tenant-boundary bypass,
- unintended write/commit behavior,
- secret or sensitive-data exposure,
- unsafe command/tool execution,
- dependency or workflow vulnerabilities,
- integrity failures that could make unverified evidence appear verified.

Scientific disagreements, model-quality questions, or non-sensitive reproducibility issues should use the normal issue templates.

## Supported code

Security fixes target the current main branch and, when practical, the latest public release. This research project does not make a production-service availability or response-time commitment.
