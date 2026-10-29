"""Exercise the real bounded client against deterministic Unix-socket peers."""

import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
                    self.state["state"]["mixes"][0]["master_db"] = params["value"]
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
