# Security Policy

## Supported Scope

Security reports are accepted for:

- Data pipeline code in `data-pipeline/`
- Website code in `website/`
- Build and deployment configuration in this repository

## Reporting a Vulnerability

Please do not open a public issue for security vulnerabilities.

Report privately using one of these channels:

1. GitHub Security Advisory for this repository
2. Email: `security@goodmeasuregiving.org`

Include:
- Affected file or component
- Reproduction steps
- Impact assessment
- Suggested fix (optional)

## Response Targets

- Initial acknowledgement: within 3 business days
- Triage and severity decision: within 7 business days
- Fix timeline: based on severity and exploitability

## Disclosure Process

- We validate and triage reports privately
- We prepare a patch and coordinate release timing
- We publish a security note after remediation

## Secrets and Credential Hygiene

- Never commit `.env` or `.env.local`
- Treat all API keys as secrets unless explicitly public by design
- Public client values must be prefixed with `VITE_` and reviewed before commit
- Run secret scans before publishing releases

## Third Party Data and Compliance

Some collectors access third party services and websites.
Operators are responsible for complying with each source Terms of Use, robots.txt, and API policies.

## Safe Harbor

We support good faith security research and will not pursue action for:
- Non destructive testing
- Responsible disclosure
- Reasonable rate and scope during validation

Please avoid data exfiltration, privacy violations, service disruption, or persistence on production systems.
