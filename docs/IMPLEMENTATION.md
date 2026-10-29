# Implementation and validation plan

## Delivery sequence

1. Select tested Omarchy/Quickshell versions and pin the canonical service
   contract revision. Define entrypoint and connection ownership.
2. Build the bounded client adapter with shared contract fixtures and explicit
   disconnected/incompatible/unsupported states.
3. Implement the bar indicator, panel, master/routes and deliberately scoped
   preset controls. Use only advertised backend capabilities.
4. Implement the explicit panel summon target and deliberate full-app launch.
5. Add a root manifest with the real entrypoint files; validate discovery,
   theme/scaling behavior and lifecycle in a separate test shell/session.
6. Validate actual service/device operation, package compatibility and the
   optional desktop-agent handoff. Publish only after those gates pass.

No root manifest is created during planning because it would advertise a
plugin whose declared entrypoints do not exist. Documentation is not an
installable prototype. Do not run the Omarchy installer against this repository
until its implementation and supported version are released.

## Automated checks

- Manifest schema, plugin ID/kinds, safe relative entrypoints and file presence.
- QML lint/static checks for the selected runtime and required imports.
- Canonical wire fixtures: version negotiation, fragmented frames, capabilities,
  baseline ordering, errors, outcome query, reconnect and bounded subscriptions.
- Component construction, server refresh and theme changes send zero mutations.
- Slider input is coalesced with one sample in flight; release preserves the
  latest final value. Own confirmations keep the preview stable; external
  changes close stale gestures. Unsupported operations have no dispatch path.
- Missing/incompatible service or module is visible and leaves writes disabled.
- Unload/reload closes owned connections without transaction replay.
- No direct USB, privileged command, kernel installation or arbitrary shell
  command can be reached from a normal control action.

## Host-session checks

Use a dedicated test session/configuration first, without overwriting the
user's current bar/audio plugin. Verify enable/disable, bar placement, summon,
theme changes, HiDPI, keyboard focus and hot reload. Repeated reloads must not
produce duplicate service subscriptions or multiple hardware writes.

Test alongside the full application, then with a direct CLI change. Both UIs
must converge on confirmed state and reject stale plans. Test service restart,
device removal/reconnect, missing full application and disabled target plugin.
The desktop agent should present exactly one configured target per validated
button event; initial/reconnected state must not open a panel.

## Installation and removal documentation

When released, document the actual repository URL and compatible versions,
separate service/module prerequisites, optional agent startup and the normal
Omarchy plugin add/enable/update/remove workflow. Do not invent a repository
URL before publication. Never use install hooks to request root or change
global audio settings.

Updates must be reviewable through the host's normal workflow. Removing or
disabling the plugin must leave the independent application/CLI usable and
must not alter the device's current mixer configuration. Do not restore a
preset merely because a UI component disappears.

Release blockers: functioning entrypoints, capability gates, protocol tests,
bounded nonblocking client, host lifecycle checks and final hardware smoke
validation. Button support is optional and evidence-gated; meters and unsupported
models are not implied by a polished interface.
