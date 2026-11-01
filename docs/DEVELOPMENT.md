# Panel development

MiniFuse for Omarchy is a small API client. Protocol, USB access and verified
hardware operations belong to MiniFuse Backend. Host integration is pinned by
`host.lock.json`; service fixtures are pinned by `contract.lock.json`.

## Checks

Requires Python 3.12–3.14, Ruff 0.17.3 and the tested Quickshell/Omarchy runtime
for host checks. From a checkout of this repository:

```sh
python3 tools/check_project.py
python3 -m unittest discover -s tests -v
ruff check client tests tools --select E4,E7,E9,F
ruff format --check client tests tools
python3 tools/check_host.py
python3 tools/check_interactions.py
```

Host tools accept `--host` for an extracted reference shell. Automated checks
use isolated configurations and contract fixtures; they do not access a real
device. Host construction, interactions, lifecycle and software meter samples
are distinct from hardware evidence. See [validation](VALIDATION.md).

## Real-service preview

```sh
python3 tools/run_preview.py
```

This explicitly opens a separate real-service control surface that can change
hardware settings. It leaves the installed bar in place and retains its own
operation evidence. Prepare hardware testing deliberately and preserve any
unresolved operation identity. It is not a fixture demonstration.

See [client architecture](PLUGIN.md), [installation and recovery](INSTALL.md),
[implementation](IMPLEMENTATION.md) and [contributing](../CONTRIBUTING.md).
Backend packaging and release work are described in the shared
[distribution roadmap](https://github.com/srdiogo/minifuse-backend/blob/main/docs/DISTRIBUTION.md)
and [release guide](https://github.com/srdiogo/minifuse-backend/blob/main/docs/RELEASING.md).
