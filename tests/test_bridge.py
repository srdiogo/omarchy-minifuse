"""Exercise the real bounded client against deterministic Unix-socket peers."""

import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bridge", ROOT / "client/bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
FIXTURE = json.loads((ROOT / "tests/contract/v1.json").read_text())


async def until(predicate, timeout=2):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("Condition did not settle")
        await asyncio.sleep(0.005)


class FramingTests(unittest.TestCase):
    def test_strict_json_and_bounds(self):
        for raw in [
            b"[]",
            b'{"x":1,"x":2}',
            b'{"x":{"a":1,"a":2}}',
            b'{"x":NaN}',
            b'{"x":Infinity}',
            b'{"x":1e999}',
            b'{"x":"\xff"}',
        ]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                bridge.decode(raw)
        with self.assertRaises(ValueError):
            bridge.decode(b"{}" + b" " * bridge.MAX_FRAME)
        with self.assertRaises(ValueError):
            bridge.encode({"value": float("inf")})
        self.assertEqual(
            bridge.decode(bridge.encode({"name": "MiniFuse · 音"})[:-1])["name"],
            "MiniFuse · 音",
        )

    def test_confirmed_silence_is_not_zero(self):
        state = copy.deepcopy(FIXTURE["state"]["result"])
        state["state"]["mixes"][0]["master_db"] = None
        mixes, _ = bridge.state_view(state)
        self.assertIsNone(mixes[0]["master_db"])
        state["state"]["mixes"][0]["master_db"] = 1
        with self.assertRaises(ValueError):
            bridge.state_view(state)

    def test_store_lock_ownership_and_archival(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "client"
            store = bridge.Store(path)
            try:
                store.save(
                    client_token="token", pending={"key": "identity", "kind": "plan"}
                )
                with self.assertRaises(BlockingIOError):
                    bridge.Store(path)
                store.resolve({"device_outcome": "unknown"}, acknowledged=True)
                self.assertIsNone(store.data["pending"])
                archived = json.loads(
                    next((path / "operations").glob("*.json")).read_text()
                )
                self.assertTrue(archived["acknowledged"])
                self.assertEqual(archived["pending"]["key"], "identity")
                for file in [store.file, *list((path / "operations").glob("*.json"))]:
                    self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            finally:
                store.close()
            os.chmod(path, 0o755)
            with self.assertRaises(ValueError):
                bridge.Store(path)

    def test_state_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            target = path / "target"
            target.write_text("{}")
            (path / "client-state.json").symlink_to(target)
            with self.assertRaises(OSError):
                bridge.Store(path)


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.runtime = Path(self.directory.name) / "runtime"
        self.runtime.mkdir(mode=0o700)
        (self.runtime / "mf-service").mkdir(mode=0o700)
        self.environment = patch.dict(
            os.environ, {"XDG_RUNTIME_DIR": str(self.runtime)}
        )
        self.environment.start()
        self.store = bridge.Store(Path(self.directory.name) / "state")
        self.app = bridge.Application(self.store)
        self.session = bridge.Session(self.app)
        self.app.session = self.session
        self.state = copy.deepcopy(FIXTURE["state"]["result"])
        self.requests = []
        self.sequence = 0
        self.record = None
        self.hold = asyncio.Event()
        self.hold.set()
        self.peers = []
        self.unsupported = False
        self.fragment = False
        self.drop_apply = False
        self.server = await asyncio.start_unix_server(
            self.peer, path=str(bridge.runtime_socket())
        )
        self.running = asyncio.create_task(self.session.run())

    async def asyncTearDown(self):
        self.running.cancel()
        await asyncio.gather(self.running, return_exceptions=True)
        for peer in self.peers:
            peer.close()
            await peer.wait_closed()
        self.server.close()
        await self.server.wait_closed()
        self.store.close()
        self.environment.stop()
        self.directory.cleanup()

    async def send(self, writer, value):
        raw = bridge.encode(value)
        if self.fragment:
            for start in range(0, len(raw), 31):
                writer.write(raw[start : start + 31])
                await writer.drain()
                await asyncio.sleep(0)
        else:
            writer.write(raw)
            await writer.drain()

    async def event(self, writer, name, data):
        self.sequence += 1
        await self.send(
            writer,
            {
                "event": name,
                "epoch": "fixture-epoch",
                "seq": self.sequence,
                "data": data,
            },
        )

    async def peer(self, reader, writer):
        self.peers.append(writer)
        try:
            while raw := await reader.readline():
                request = json.loads(raw)
                self.requests.append(request)
                method, params = request["method"], request["params"]
                error = None
                if method == "hello":
                    result = FIXTURE["hello"]["result"]
                elif method == "subscribe":
                    caps = {**self.state["capabilities"], "mixer": not self.unsupported}
                    device = {
                        "device_id": "fixture-device_id",
                        "generation": "fixture-generation",
                        "connection": "ready",
                        "capabilities": caps,
                    }
                    result = {
                        "epoch": "fixture-epoch",
                        "seq": self.sequence,
                        "devices": [device],
                        "states": [] if self.unsupported else [self.state],
                    }
                elif method == "begin_control":
                    assert (
                        self.store.data["pending"]["key"] == params["idempotency_key"]
                    )
                    self.record = copy.deepcopy(FIXTURE["live_begin"]["result"])
                    result = self.record
                elif method == "update_control":
                    result = {
                        "accepted": True,
                        "operation_id": "fixture-operation_id",
                        "sequence": params["sequence"],
                    }
                    await self.send(
                        writer, {"api": 1, "id": request["id"], "result": result}
                    )
                    await self.hold.wait()
                    target = next(
                        r["params"]["target"]
                        for r in reversed(self.requests)
                        if r["method"] == "begin_control"
                    )
                    mix = next(
                        m
                        for m in self.state["state"]["mixes"]
                        if m["mix"] == target["mix"]
                    )
                    if target["kind"] == "master_level":
                        mix["master_db"] = params["value"]
                    else:
                        channel = next(
                            c
                            for c in mix["channels"]
                            if c["channel"] == target["source"]
                        )
                        channel[
                            "derived_level_db"
                            if target["kind"] == "channel_level"
                            else "derived_pan"
                        ] = params["value"]
                    self.state["revision"] = "revision-" + str(params["sequence"])
                    result = copy.deepcopy(
                        FIXTURE[
                            "live_finished" if params["finish"] else "live_updated"
                        ]["result"]
                    )
                    result["sample_sequence"] = params["sequence"]
                    result["state"] = self.state["state"]
                    result["samples"] = [
                        {
                            "sequence": params["sequence"],
                            "value": params["value"],
                            "finish": params["finish"],
                        }
                    ]
                    self.record = result
                    await self.event(
                        writer,
                        "state_changed",
                        {**self.state, "operation_id": "fixture-operation_id"},
                    )
                    await self.event(
                        writer,
                        "operation_finished" if params["finish"] else "control_updated",
                        result,
                    )
                    continue
                elif method == "cancel_control":
                    result = copy.deepcopy(FIXTURE["live_finished"]["result"])
                    result["gesture_end"] = "cancelled"
                    self.record = result
                elif method == "plan_changes":
                    change = params["changes"][0]
                    if change["kind"] == "route":
                        assert set(change) == {"kind", "mix", "source"}
                    result = FIXTURE["plan"]["result"]
                elif method == "apply_plan":
                    assert (
                        self.store.data["pending"]["key"] == params["idempotency_key"]
                    )
                    self.record = copy.deepcopy(FIXTURE["finished"]["result"])
                    if self.drop_apply:
                        writer.close()
                        return
                    result = FIXTURE["accepted"]["result"]
                elif method == "get_operation":
                    if self.record:
                        result = self.record
                    else:
                        error = {
                            "code": "outcome_unknown",
                            "message": "No retained operation matches this client identity",
                        }
                else:
                    raise AssertionError(method)
                await self.send(
                    writer,
                    {
                        "api": 1,
                        "id": request["id"],
                        **({"error": error} if error else {"result": result}),
                    },
                )
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            writer.close()

    async def ready(self):
        await until(lambda: self.app.connected)

    def method_requests(self, name):
        return [r for r in self.requests if r["method"] == name]

    async def test_baseline_and_fragmentation_have_zero_mutations(self):
        self.fragment = True
        await self.ready()
        self.assertEqual([r["method"] for r in self.requests], ["hello", "subscribe"])
        self.assertTrue(self.app.writable())
        self.assertEqual(
            self.app.mix()["master_db"], self.state["state"]["mixes"][0]["master_db"]
        )
        for _ in range(100):
            self.app.publish()
        self.assertEqual(self.app.output.qsize(), 1)

    async def test_channel_level_has_fixed_target_and_preserves_release(self):
        await until(lambda: self.app.connected)
        self.hold.clear()
        self.app.command(
            {"action": "level", "source": "analog1", "value": -18, "finish": False}
        )
        await until(lambda: any(r["method"] == "update_control" for r in self.requests))
        self.app.command(
            {"action": "level", "source": "analog2", "value": 12, "finish": True}
        )
        for n in range(20):
            self.app.command(
                {
                    "action": "level",
                    "source": "analog1",
                    "value": -16 + n / 2,
                    "finish": False,
                }
            )
        self.app.command(
            {"action": "level", "source": "analog1", "value": -6, "finish": True}
        )
        self.hold.set()
        await until(
            lambda: not self.store.data.get("pending") and self.session.live is None
        )
        begin = next(r for r in self.requests if r["method"] == "begin_control")
        self.assertEqual(
            begin["params"]["target"],
            {"kind": "channel_level", "mix": "out12", "source": "analog1"},
        )
        updates = [
            r["params"] for r in self.requests if r["method"] == "update_control"
        ]
        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[-1]["value"], -6)
        self.assertTrue(updates[-1]["finish"])
        self.assertEqual(self.app.mix()["channels"][0]["level_db"], -6)

    async def test_pan_range_silence_and_unadvertised_source(self):
        await until(lambda: self.app.connected)
        for action, source, value in [
            ("pan", "analog1", None),
            ("pan", "analog1", 1.1),
            ("level", "analog1", 12.1),
            ("level", "usb6", -6),
        ]:
            with self.assertRaises(ValueError):
                self.app.command(
                    {"action": action, "source": source, "value": value, "finish": True}
                )
        self.app.command(
            {"action": "pan", "source": "analog1", "value": 0.25, "finish": True}
        )
        await until(lambda: self.session.task and self.session.task.done())
        self.assertEqual(self.app.mix()["channels"][0]["pan"], 0.25)
        self.app.command(
            {"action": "level", "source": "analog1", "value": None, "finish": True}
        )
        await until(lambda: self.session.task.done())
        self.assertIsNone(self.app.mix()["channels"][0]["level_db"])

    async def test_solo_uses_typed_channel_plan(self):
        await until(lambda: self.app.connected)
        self.app.command({"action": "solo", "source": "analog1", "value": True})
        await until(lambda: self.session.task and self.session.task.done())
        plan = next(r for r in self.requests if r["method"] == "plan_changes")
        self.assertEqual(
            plan["params"]["changes"],
            [{"kind": "channel", "mix": "out12", "source": "analog1", "solo": True}],
        )

    async def test_meters_are_visible_only_ephemeral_and_expire(self):
        await until(lambda: self.app.connected)
        self.assertNotIn("meters_updated", self.requests[1]["params"]["events"])
        self.state["capabilities"]["signal_meters"] = True
        self.app.command({"action": "watch", "value": True})
        await until(
            lambda: len([r for r in self.requests if r["method"] == "subscribe"]) == 2
        )
        await until(lambda: self.app.state["capabilities"]["signal_meters"])
        initial = copy.deepcopy(self.app.state)
        await self.event(self.peers[0], "meters_updated", FIXTURE["meters"]["data"])
        await until(lambda: self.app.meters is not None)
        self.assertEqual(self.app.state, initial)
        self.assertFalse(self.store.data.get("pending"))
        await until(lambda: self.app.meters is None)
        self.app.command({"action": "watch", "value": False})
        await until(
            lambda: len([r for r in self.requests if r["method"] == "subscribe"]) == 3
        )
        self.assertNotIn("meters_updated", self.requests[-1]["params"]["events"])
        self.assertTrue(
            all(r["method"] in ("hello", "subscribe") for r in self.requests)
        )

    async def test_visibility_subscription_preserves_recovery_warning(self):
        await until(lambda: self.app.connected)
        self.app.uncertain = True
        self.app.message = "Outcome uncertain; inspect before acknowledging"
        self.app.command({"action": "watch", "value": True})
        await until(
            lambda: len([r for r in self.requests if r["method"] == "subscribe"]) == 2
        )
        await asyncio.sleep(0.05)
        self.assertTrue(self.app.uncertain)
        self.assertEqual(
            self.app.message, "Outcome uncertain; inspect before acknowledging"
        )
        self.assertFalse(self.app.writable())

    async def test_meter_identity_and_shapes_are_checked(self):
        await until(lambda: self.app.connected)
        self.app.visible = True
        self.app.state["capabilities"]["signal_meters"] = True
        data = copy.deepcopy(FIXTURE["meters"]["data"])
        data["generation"] = "old-generation"
        self.session.event("meters_updated", data)
        self.assertIsNone(self.app.meters)
        data["generation"] = self.app.state["generation"]
        data["sources_dbfs"] = [float("nan")] * 10
        with self.assertRaises(ValueError):
            self.session.event("meters_updated", data)
        self.assertIsNone(self.app.meters)

    async def test_coalescing_waits_for_settlement_and_preserves_release(self):
        await self.ready()
        self.hold.clear()
        self.app.command({"action": "master", "value": -12, "finish": False})
        await until(lambda: bool(self.method_requests("update_control")))
        for n in range(100):
            self.app.command(
                {"action": "master", "value": -20 + n / 10, "finish": False}
            )
        self.app.command({"action": "master", "value": -6, "finish": True})
        self.assertEqual(len(self.method_requests("update_control")), 1)
        self.hold.set()
        await until(
            lambda: (
                len(self.method_requests("update_control")) == 2
                and self.store.data.get("pending") is None
            )
        )
        updates = self.method_requests("update_control")
        self.assertEqual([u["params"]["sequence"] for u in updates], [1, 2])
        self.assertEqual(updates[-1]["params"]["value"], -6)
        self.assertTrue(updates[-1]["params"]["finish"])
        await until(lambda: self.session.task.done())
        self.assertFalse(json.loads(self.app.output.get_nowait())["busy"])

    async def test_route_is_capability_gated_and_uses_domain_source(self):
        await self.ready()
        with self.assertRaises(ValueError):
            self.app.command({"action": "route", "value": "usb56"})
        self.app.command({"action": "route", "value": "usb12"})
        await until(
            lambda: (
                bool(self.method_requests("apply_plan"))
                and self.store.data.get("pending") is None
            )
        )
        change = self.method_requests("plan_changes")[0]["params"]["changes"][0]
        self.assertEqual(change, {"kind": "route", "mix": "out12", "source": "usb12"})

    async def test_source_mute_uses_only_advertised_source(self):
        await self.ready()
        with self.assertRaises(ValueError):
            self.app.command({"action": "mute", "source": "usb6", "value": True})
        self.app.command({"action": "mute", "source": "usb1", "value": True})
        await until(lambda: bool(self.method_requests("plan_changes")))
        self.assertEqual(
            self.method_requests("plan_changes")[0]["params"]["changes"][0]["kind"],
            "channel",
        )

    async def test_unsupported_model_keeps_controls_disabled(self):
        self.unsupported = True
        await self.ready()
        self.assertFalse(self.app.writable())
        self.app.command({"action": "master", "value": -6, "finish": True})
        self.assertFalse(self.method_requests("begin_control"))

    async def test_direct_route_disables_bypassed_master(self):
        self.state["state"]["mixes"][0]["route"] = "usb12"
        await self.ready()
        self.app.command({"action": "master", "value": -6, "finish": True})
        self.assertFalse(self.method_requests("begin_control"))

    async def test_external_state_stops_gesture_without_final_replay(self):
        await self.ready()
        self.app.command({"action": "master", "value": -12, "finish": False})
        await until(lambda: self.record and self.record.get("sample_sequence") == 1)
        external = copy.deepcopy(self.state)
        external["revision"] = "external-revision"
        await self.event(self.peers[-1], "state_changed", external)
        await until(lambda: bool(self.method_requests("cancel_control")))
        await until(lambda: self.store.data.get("pending") is None)
        self.assertEqual(len(self.method_requests("update_control")), 1)

    async def test_sequence_gap_invalidates_connection(self):
        await self.ready()
        self.sequence += 1
        await self.event(self.peers[-1], "state_changed", self.state)
        await until(lambda: self.running.done())
        self.assertIsInstance(self.running.exception(), ValueError)

    async def test_uncertain_apply_retains_identity_without_replaying(self):
        self.drop_apply = True
        await self.ready()
        self.app.command({"action": "route", "value": "usb12"})
        await until(lambda: self.running.done())
        self.assertIsNotNone(self.store.data.get("pending"))
        self.assertEqual(len(self.method_requests("apply_plan")), 1)
        self.assertTrue(self.app.uncertain)
        await asyncio.gather(self.running, return_exceptions=True)
        self.running = asyncio.create_task(self.reconnect())
        await until(
            lambda: self.app.connected and self.store.data.get("pending") is None
        )
        self.assertEqual(len(self.method_requests("apply_plan")), 1)
        self.assertTrue(self.method_requests("get_operation"))

    async def reconnect(self):
        self.app.connected = False
        self.session = bridge.Session(self.app)
        self.app.session = self.session
        await self.session.run()

    async def test_unknown_identity_requires_explicit_acknowledgement(self):
        await self.ready()
        self.store.save(pending={"key": "lost-key", "kind": "plan"})
        await self.session.query()
        self.assertTrue(self.app.uncertain)
        self.assertTrue(self.app.can_acknowledge)
        self.app.command({"action": "master", "value": -6, "finish": True})
        self.assertFalse(self.method_requests("begin_control"))
        self.app.command({"action": "acknowledge"})
        self.assertIsNone(self.store.data.get("pending"))
        self.assertTrue(list((self.store.path / "operations").glob("*.json")))

    async def test_pending_operation_cannot_be_acknowledged(self):
        await self.ready()
        self.store.save(pending={"key": "pending", "kind": "live_control"})
        self.app.uncertain = True
        self.app.can_acknowledge = True
        self.record = FIXTURE["live_begin"]["result"]
        await self.session.query()
        self.app.command({"action": "acknowledge"})
        self.assertIsNotNone(self.store.data.get("pending"))
        self.assertFalse(self.app.can_acknowledge)

    async def test_rejected_sample_does_not_discard_admitted_gesture_identity(self):
        await self.ready()
        self.store.save(pending={"key": "admitted-key", "kind": "live_control"})
        self.session.operation_id = "fixture-operation_id"
        self.session.failed(
            bridge.ApiError(
                {
                    "code": "control_busy",
                    "message": "Sample rejected",
                    "details": {"device_write_attempted": False},
                }
            )
        )
        self.assertIsNotNone(self.store.data.get("pending"))
        self.assertTrue(self.app.uncertain)

    async def test_storage_failure_prevents_admission(self):
        await self.ready()
        with patch.object(
            self.store, "save", side_effect=OSError("State store unavailable")
        ):
            self.app.command({"action": "master", "value": -6, "finish": True})
            await until(lambda: self.session.task.done())
        self.assertFalse(self.method_requests("begin_control"))
        self.assertFalse(self.method_requests("update_control"))
        self.assertIn("State store unavailable", self.app.message)

    async def test_application_launch_is_detached_from_client_lifetime(self):
        await self.ready()
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired("minifuse-control", 0.25)
        with patch.object(bridge.subprocess, "Popen", return_value=process) as launch:
            await self.app.open_app()
        self.assertEqual(launch.call_args.args, (["minifuse-control"],))
        self.assertTrue(launch.call_args.kwargs["start_new_session"])
        self.assertIn(process, self.app.applications)
        self.running.cancel()
        await asyncio.gather(self.running, return_exceptions=True)
        process.terminate.assert_not_called()
        process.kill.assert_not_called()

    async def test_missing_application_reports_installation_feedback(self):
        await self.ready()
        with patch.object(bridge.subprocess, "Popen", side_effect=FileNotFoundError):
            await self.app.open_app()
        self.assertIn("Install MiniFuse Control", self.app.message)

    async def test_partial_frame_deadline(self):
        await self.ready()
        self.peers[-1].write(b'{"event":')
        await self.peers[-1].drain()
        await until(lambda: self.running.done(), timeout=3)
        self.assertIsInstance(self.running.exception(), asyncio.TimeoutError)

    async def test_oversized_frame_closes_connection(self):
        await self.ready()
        self.peers[-1].write(b"{" + b"x" * bridge.MAX_FRAME)
        await self.peers[-1].drain()
        await until(lambda: self.running.done())
        self.assertIsInstance(self.running.exception(), asyncio.LimitOverrunError)


if __name__ == "__main__":
    unittest.main()
