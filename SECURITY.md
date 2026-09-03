# Security Policy

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, private
addresses, or logs. Use GitHub's private vulnerability-reporting feature for
this repository. If private reporting is unavailable, open a minimal issue
asking the maintainer to establish a private channel; omit technical details.

Include the affected version/commit, prerequisites, impact, a minimal
reproduction, and suggested remediation. Remove tokens, API keys, cookies,
serial numbers, System IDs, MAC addresses, and account data.

## Response targets

These are project targets, not an SLA: acknowledge critical/high reports in
three business days, establish severity and containment in seven, and publish
a coordinated fix/advisory as soon as safely validated. Lower-severity issues
are prioritized by exploitability and impact.

## Supported version

Only the latest published release and the default branch receive security
fixes. Operators should keep Home Assistant and this integration current and
retain a tested rollback/backup of their configuration.

## Security boundaries

Kidde HomeSafe is a privileged Home Assistant integration, not a sandbox. It
stores a Kidde cloud session cookie (cloud path) in the config entry, which
Home Assistant's storage protects at rest the same way it protects any other
integration's credentials; it does not add its own encryption layer. The BLE
path is passive-only: it never connects to or writes to an alarm, and the
raw advertisement status payload it exposes is unmapped diagnostic data, not
a verified alarm or fault signal (see docs/BLE_PROTOCOL.md). Downloaded
diagnostics redact serial-like service data, System ID, and account
credentials.
