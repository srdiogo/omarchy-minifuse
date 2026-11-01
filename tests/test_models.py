"""Per-model views use synthetic data and never issue USB commands."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

import test_bridge as tests

bridge = tests.bridge
ROOT = Path(__file__).resolve().parents[1]
MODELS = json.loads((ROOT / "tests/contract/model-profiles-v1.json").read_text())


class ModelTests(unittest.TestCase):
    def test_profiles_select_input_only_views_and_never_grant_mixer_writes(self):
        for model in MODELS["devices"]:
            profile = model["profile"]
            if profile["id"] == "mf4":
                continue
            with tempfile.TemporaryDirectory() as directory:
                store = bridge.Store(Path(directory) / "state")
                try:
                    app = bridge.Application(store)
                    session = bridge.Session(app)
                    session.epoch = "epoch"
                    normal = profile["device_mode"] == "control"
                    device = dict(
                        model=profile["model"],
                        profile=profile,
                        device_id="device",
                        generation="generation",
                        connection="ready" if normal else "unavailable",
                        capabilities=dict(mixer=False, switch_readback=normal),
                    )
                    inputs = {c["target"]: False for c in profile["input_controls"]}
                    state = dict(
                        device_id="device",
                        generation="generation",
                        revision="revision",
                        capabilities=device["capabilities"],
                        state=dict(
                            layout="minifuse-basic-b2-v1",
                            model=profile["model"],
                            mixes=[],
                            inputs=inputs,
                        ),
                    )
                    session.baseline(
                        dict(
                            epoch="epoch",
                            seq=0,
                            devices=[device],
                            states=[state] if normal else [],
                        )
                    )
                    app.connected = True
                    app.publish()
                    view = bridge.decode(app.output.get_nowait()[:-1])
                    self.assertEqual(view["layout"], profile["layout"])
                    self.assertEqual(view["inputs"], inputs)
                    self.assertEqual(view["mixes"], [])
                    self.assertFalse(view["can_write"])
                    self.assertEqual(view["model_name"], profile["model"])
                    self.assertEqual(len(view["input_controls"]), len(inputs))
                    with self.assertRaises(ValueError):
                        app.command(
                            dict(
                                action="input_switch",
                                target="phantom_power",
                                value=True,
                            )
                        )
                    self.assertIsNone(store.data.get("pending"))
                    session.baseline(
                        dict(
                            epoch="epoch",
                            seq=0,
                            devices=[device, device],
                            states=[state],
                        )
                    )
                    self.assertIsNone(app.state)
                    self.assertIsNone(app.device)
                finally:
                    store.close()

    def test_basic_state_rejects_mf4_mixers_missing_inputs_and_non_boolean_values(self):
        model = MODELS["devices"][0]
        state = dict(
            device_id="device",
            generation="generation",
            revision="revision",
            capabilities=dict(mixer=False, switch_readback=True),
            state=dict(
                layout="minifuse-basic-b2-v1",
                model=model["profile"]["model"],
                mixes=[],
                inputs={c["target"]: False for c in model["profile"]["input_controls"]},
            ),
        )
        bridge.state_view(state)
        for mutate in (
            lambda s: s["capabilities"].update(mixer=True),
            lambda s: s["state"]["inputs"].pop("direct_monitor"),
            lambda s: s["state"]["inputs"].update(inst1=1),
            lambda s: s["state"].update(model="Unknown"),
        ):
            malformed = copy.deepcopy(state)
            mutate(malformed)
            with self.assertRaises(ValueError):
                bridge.state_view(malformed)

    def test_unknown_and_inconsistent_profiles_are_not_accepted(self):
        for key, value in (
            ("schema_version", 2),
            ("schema_version", True),
            ("id", "future"),
            ("layout", "mf4_mixer"),
        ):
            device = copy.deepcopy(MODELS["devices"][0])
            device["profile"][key] = value
            self.assertEqual(bridge.model_profile(device), {})


if __name__ == "__main__":
    unittest.main()
