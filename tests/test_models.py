"""Per-model views use synthetic data and never issue USB commands."""

import copy
import hashlib
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
        lock = json.loads((ROOT / "model-contract.lock.json").read_text())
        for fixture in lock["fixtures"]:
            self.assertEqual(
                hashlib.sha256((ROOT / fixture["path"]).read_bytes()).hexdigest(),
                fixture["sha256"],
            )
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


NATIVE = json.loads((ROOT / "tests/contract/loopback-v1.json").read_text())["devices"]


class NativeLoopbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_state_routes_live_intents_and_meter_shapes_follow_each_model(
        self,
    ):
        for fixture in NATIVE:
            with tempfile.TemporaryDirectory() as directory:
                store = bridge.Store(Path(directory) / "state")
                try:
                    app = bridge.Application(store)
                    session = bridge.Session(app)
                    app.session = session
                    app.device = copy.deepcopy(fixture["device"])
                    app.state = copy.deepcopy(fixture["state"])
                    app.connected = True
                    app.visible = True
                    app.publish()
                    view = bridge.decode(app.output.get_nowait()[:-1])
                    self.assertTrue(view["can_write"])
                    self.assertEqual(view["selected"], "loopback")
                    self.assertFalse(view["mixes"][0]["channels"][1]["solo_available"])
                    self.assertFalse(
                        next(
                            c
                            for c in view["mixes"][0]["channels"]
                            if c["source"] == "usb12"
                        )["pan_available"]
                    )
                    session.event("meters_updated", fixture["meters"])
                    self.assertEqual(
                        app.meters["loopback"], fixture["meters"]["loopback_dbfs"]
                    )
                    malformed = copy.deepcopy(fixture["meters"])
                    malformed["loopback_dbfs"] = [0]
                    with self.assertRaises(ValueError):
                        session.event("meters_updated", malformed)
                    for command in (
                        dict(action="solo", source="analog1", value=True),
                        dict(action="pan", source="usb12", value=0.5, finish=True),
                        dict(action="otg_routing", field="meter_source", value=4),
                    ):
                        with self.assertRaises(ValueError):
                            session.command(command)
                    from unittest.mock import AsyncMock

                    session.change = AsyncMock()
                    session.command(
                        dict(action="loopback_routing", field="monitor", value=True)
                    )
                    await session.task
                    session.change.assert_awaited_once_with(
                        dict(kind="loopback_routing", monitor=True)
                    )
                    if fixture["device"]["profile"]["id"] == "mf2_otg":
                        session.change.reset_mock()
                        session.command(
                            dict(action="otg_routing", field="meter_source", value=3)
                        )
                        await session.task
                        session.change.assert_awaited_once_with(
                            dict(kind="otg_routing", meter_source=3)
                        )
                    session.live_control = AsyncMock()
                    session.command(
                        dict(action="level", source="usb12", value=-18.0, finish=False)
                    )
                    await session.task
                    self.assertEqual(
                        session.live["target"],
                        dict(kind="channel_level", mix="loopback", source="usb12"),
                    )
                    session.live = None
                    app.device["firmware"]["raw_bcd"] = 0
                    self.assertFalse(app.writable())
                    app.device["firmware"] = None
                    self.assertFalse(app.writable())
                    app.device.pop("firmware")
                    self.assertFalse(app.writable())
                    self.assertIsNone(store.data.get("pending"))
                finally:
                    store.close()

    async def test_native_malformed_or_unconfirmed_firmware_cannot_expose_a_mixer(self):
        for modify in (
            lambda s: s["state"].update(firmware=None),
            lambda s: s["state"].update(loopback=None),
            lambda s: s["state"]["firmware"].pop("version"),
            lambda s: s["state"]["firmware"].update(loopback_compatible=False),
            lambda s: s["state"]["loopback"].update(enabled=1),
            lambda s: s["state"]["mixes"][0]["channels"].pop(),
            lambda s: s["state"]["mixes"][0]["channels"][0].update(solo=True),
            lambda s: s["state"]["mixes"][0].update(route="usb12"),
        ):
            malformed = copy.deepcopy(NATIVE[1]["state"])
            modify(malformed)
            with self.assertRaises(ValueError):
                bridge.state_view(malformed)


if __name__ == "__main__":
    unittest.main()
