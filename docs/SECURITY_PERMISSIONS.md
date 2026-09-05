# Permission Architecture

PrometheanOS treats a future local AI assistant as an untrusted request source.
Prompt content, retrieved documents, model output, and tool results can contain
malicious instructions. None of them grant authority.

## Trust boundary

The permission broker in `src/system/security/permissions.py` is the policy
boundary between an assistant and system-affecting operations. Callers submit a
named operation, target, reason, and requesting component. The broker only
recognizes operations in its allowlist and records every decision.

There is deliberately no `AI -> sudo -> arbitrary command` path and no API
endpoint that accepts a shell command. Future implementations must register
specific operations rather than exposing a general command runner. A handler
must be narrowly scoped to its operation and must perform its own target
validation.

## Permission levels

- `SAFE`: read-only diagnostics, hardware inspection, and system status. A safe
  operation still needs a registered implementation before it can run.
- `CONFIRMATION_REQUIRED`: package installation, configuration changes, service
  stops, and file deletion. Each request needs explicit user confirmation.
- `HIGH_RISK`: boot configuration, partition changes, firewall changes, and
  privileged system modifications. These are allowlisted for policy visibility,
  but always require explicit confirmation and a separately reviewed handler.

The broker never changes BIOS settings, disables security controls, modifies
kernel parameters, kills unrelated processes, or performs implicit cleanup.

## Audit logging

Audit events contain the requested operation, sanitized target, requesting
component, UTC timestamp, result, and whether confirmation occurred. Commands,
passwords, API keys, tokens, and secret-looking values are not recorded. The
default logger is in-memory; a deployment may provide an explicit JSONL path
with suitable filesystem permissions.

Audit logs support accountability, not authorization. A log entry never makes
an operation safe or grants permission.

## Attack surface and assumptions

- The local API is a control-plane interface, not a trust proof. It must remain
  bound to an appropriately protected local interface and should gain caller
  authentication before remote access is supported.
- Prompt injection is expected. User-confirmation state must come from a
  separate trusted UI or operator flow, never from model text.
- Operation names and targets are untrusted input. Unknown names, missing
  context, and unregistered implementations are rejected.
- Privilege separation remains a deployment concern. The service should run as
  an unprivileged user; future privileged helpers must be narrowly scoped,
  separately audited, and independently constrained.
- Denial of service, filesystem races, compromised dependencies, and a
  compromised local user are residual risks that require OS-level controls.