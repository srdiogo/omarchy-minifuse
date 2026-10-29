# MiniFuse for Omarchy

Planned compact MiniFuse control panel for the Quickshell-based Omarchy shell.

**Project status: planning documents only.** No root plugin manifest or QML
entrypoint is shipped yet, so this repository is not an installable plugin.
There is no placeholder panel claiming to control hardware.

## Scope

Provide a bar indicator and quick panel for connection status, the selected
mix's master, supported mute/routes, named preset access and an action to open
the full application. Use `mf-service` for state and operations. Keep USB,
kernel-module loading and protocol logic outside the shell process.

The full standalone application is a separate project. This plugin does not
replace Omarchy's normal PipeWire volume/application mixer; the MiniFuse's
hardware mix master and host volume are distinct controls.

## Documents

- [Plugin architecture and host contract](docs/PLUGIN.md)
- [Implementation, installation and validation plan](docs/IMPLEMENTATION.md)

The canonical API contract is `mf-service/docs/IPC.md` (draft major 1). Depend
on a pinned compatible revision. The overall platform milestones live in the
`mf-cli` repository under `docs/platform/DELIVERY.md`.

## Project boundary

The plugin presents state and explicit control actions. The service serializes
its clients; `mf-core` validates the hardware operations. The separately
packageable desktop agent from `minifuse-control` owns physical-button launch
policy and can request this panel. The plugin never opens the GUI automatically
because it received the same button event.

User click/keyboard access works without the optional hardware-button feature.
Unknown switch state and unavailable meters stay unavailable. Firmware,
effects, raw USB commands, device-storage writes and inferred MF1/MF2 mixer
support are outside scope.

## Distribution intent

Use plugin ID `srdiogo.minifuse`. Once implemented and validated, ship a real
`manifest.json` at the repository root with its QML entrypoints. This matches
the Omarchy installer contract. Service and optional desktop integration are
separate prerequisites, not installer hooks hidden in the plugin.

Nothing in this repository changes `~/.config/omarchy`, restarts the shell or
enables a plugin today. New project-owned material is [MIT licensed](LICENSE).
This is an independent community project, not an official Arturia/Omarchy app.
