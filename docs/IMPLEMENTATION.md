# Implementation and acceptance status

The planning stage is implemented as three real entrypoints with one connection
owner. `manifest.json` declares the service, bar widget and summonable panel;
its paths are validated by project checks and the pinned host registry.

Implemented:

- API negotiation, bounded framing, same-UID peer validation, atomic baseline,
  capability gates and contiguous subscriptions.
- Connection indicator, mix selection, continuous master control, routes and
  per-source mute. A bypassed master is disabled with a reason.
- Confirmed INST/+48 V indicators, fixed-height status feedback and host theme,
  scale and keyboard conventions.
- Durable operation identity, intermediate/final settlement, reconnect queries,
  explicit unknown-outcome acknowledgement and private evidence archives.
- Explicit summon target and deliberate full-app launch with missing-app feedback.
- Contract tests, real host-component construction, pinned host checks, CI and
  isolated preview tooling.

The full application deliberately owns preset inspection/comparison/restore,
detailed mixing, writable input switches and signal meters. The compact panel
has no fabricated master-mute operation and no physical-button subscription.
MF1/MF2 remain capability-gated; their MF4 mixer layouts are never inferred.

See [validation evidence](VALIDATION.md) for the distinction between deterministic
fixture tests, isolated host tests and actual MF4 validation. Remaining broader
acceptance includes additional monitors/scaling combinations, host releases,
service/module/kernel combinations, device models and clean-machine installation.
Logo-button decoding/activation is a separate evidence gate. Firmware, effects
and device-storage writes remain outside scope.
