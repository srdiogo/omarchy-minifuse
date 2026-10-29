# Contributing

Contributions are welcome through focused pull requests with English code,
documentation and commit messages. Use the configured human contributor identity
and purpose-based `feature/`, `fix/` or `docs/` branch names. Preserve attribution.

Device protocol, selector conversion, USB access and transaction recovery belong
in mf-core/mf-service. Keep this project a small client of the canonical API.
New controls must follow advertised capabilities; do not infer MF4 layouts for
other devices. Do not add firmware, effects, device-storage writers, privilege
requests or global host audio changes.

Run:

```sh
python3 tools/check_project.py
python3 -m unittest discover -s tests -v
ruff check client tests tools --select E4,E7,E9,F
ruff format --check client tests tools
python3 tools/check_host.py
python3 tools/check_interactions.py
```

CI pins Ruff 0.17.3. Host checks need Quickshell and the Omarchy modules selected
by `host.lock.json`; `--host` accepts an extracted reference shell directory.
Automated checks use fixtures/isolated runtime directories and do not access a
real device. `tools/run_preview.py` is explicitly a real-service control surface.

A service contract update must retain the canonical fixture's producer revision
and SHA-256. A host update must record the source revision/archive checksum and
repeat construction, lifecycle, theme/scaling and keyboard checks. Avoid broad
compatibility claims based on a moving branch or successful lint alone.

Report hardware results with model, kernel/module/service versions, exact scope,
verification and restoration evidence. Never attach private client tokens,
operation journals, USB captures, user presets or host diagnostics without
reviewing their contents. Keep unresolved operation identities during debugging.
