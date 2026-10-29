#!/usr/bin/env python3
"""Bounded, standard-library client for the MiniFuse Omarchy plugin.

Device semantics and all USB operations belong to mf-service/mf-core. This
process owns one socket and durable client identity for every plugin view.
"""

import argparse
import asyncio
import contextlib
import fcntl
import itertools
import json
import math
import os
from pathlib import Path
import secrets
import signal
import socket
import stat
import struct
import subprocess
import sys
import time

MAX_FRAME = 256 * 1024
MAX_COMMAND = 4096
MAX_VIEW = 32 * 1024
EVENTS = [
    "device_added",
    "device_removed",
    "capabilities_changed",
    "state_changed",
    "operation_finished",
    "control_updated",
]


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def decode(raw, limit=MAX_FRAME - 2):
    if len(raw) + 1 > limit:
        raise ValueError("Frame exceeds its limit")

    def invalid(value):
        raise ValueError("Nonfinite JSON number")

    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Nonfinite JSON number")
        return number

    result = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=unique,
        parse_constant=invalid,
        parse_float=finite,
    )
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


def encode(value, limit=MAX_FRAME - 2):
    raw = json.dumps(value, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    if len(raw) > limit:
        raise ValueError("Frame exceeds its limit")
    return raw


def opaque(value):
    return isinstance(value, str) and 0 < len(value) <= 128


def runtime_socket():
    path = Path(os.environ.get("XDG_RUNTIME_DIR", ""))
    if not path.is_absolute():
        raise ValueError("XDG_RUNTIME_DIR must be an absolute private directory")
    info = path.stat()
    if (
        info.st_uid != os.geteuid()
        or info.st_mode & 0o077
        or not stat.S_ISDIR(info.st_mode)
    ):
        raise ValueError("Invalid runtime directory ownership or permissions")
    return path / "mf-service/control.sock"


def private_directory(path):
    if not path.is_absolute():
        raise ValueError("State location must be absolute")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_mode & 0o077
    ):
        raise ValueError("Invalid private state directory")
    return path


def read_private(path, limit=16384):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
        ):
            raise ValueError("Invalid private state file")
        return decode(stream.read(limit + 1), limit + 1)


class Store:
    """Persist an identity before admission; archive results before clearing it."""

    def __init__(self, directory=None):
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
        self.path = private_directory(directory or base / "omarchy-minifuse")
        self.lock = os.open(
            self.path / "bridge.lock", os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600
        )
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.file = self.path / "client-state.json"
            try:
                self.data = read_private(self.file)
            except FileNotFoundError:
                self.data = {}
            if set(self.data) - {"client_token", "pending"}:
                raise ValueError("Unknown client-state fields")
            if "client_token" in self.data and not opaque(self.data["client_token"]):
                raise ValueError("Invalid retained client token")
            pending = self.data.get("pending")
            if pending is not None and (
                not isinstance(pending, dict)
                or set(pending) != {"key", "kind"}
                or not opaque(pending["key"])
                or pending["kind"] not in ("live_control", "plan")
            ):
                raise ValueError("Invalid retained operation identity")
        except BaseException:
            os.close(self.lock)
            raise

    def save(self, **changes):
        data = {**self.data, **changes}
        raw = encode(data, 16384)
        temporary = self.path / (".state-" + secrets.token_hex(12))
        try:
            with os.fdopen(
                os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
            ) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.file)
            self.sync()
            self.data = data
        finally:
            temporary.unlink(missing_ok=True)

    def sync(self):
        descriptor = os.open(self.path, os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def resolve(self, record, acknowledged=False):
        pending = self.data.get("pending")
        if not pending:
            return
        archive = private_directory(self.path / "operations")
        with os.scandir(archive) as entries:
            if len(list(itertools.islice(entries, 257))) >= 256:
                raise ValueError(
                    "Operation archive is full; retain and archive resolved evidence"
                )
        # Keys are generated locally; never use a service-provided identifier as a path.
        filename = secrets.token_hex(24) + ".json"
        value = {"pending": pending, "record": record, "acknowledged": acknowledged}
        with os.fdopen(
            os.open(archive / filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
            "wb",
        ) as stream:
            stream.write(encode(value))
            stream.flush()
            os.fsync(stream.fileno())
        descriptor = os.open(archive, os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.save(pending=None)

    def close(self):
        os.close(self.lock)


class SubscriptionRefresh(Exception):
    """Replace the connection after its current control work has settled."""


class ApiError(Exception):
    def __init__(self, error):
        self.error = error
        super().__init__(
            str(error.get("message", "Service rejected the request"))[:240]
        )


def state_view(value):
    if not isinstance(value, dict) or not all(
        opaque(value.get(k)) for k in ("device_id", "generation", "revision")
    ):
        raise ValueError("Invalid confirmed-state identity")
    caps, state = value.get("capabilities", {}), value.get("state", {})
    if not isinstance(caps, dict) or not isinstance(state, dict):
        raise ValueError("Invalid state or capability object")
    mixes = state.get("mixes", [])
    allowed = caps.get("mixes", [])
    if (
        not isinstance(mixes, list)
        or len(mixes) > 16
        or not isinstance(allowed, list)
        or len(allowed) > 16
    ):
        raise ValueError("Invalid mix collection")
    if any(not isinstance(c, dict) for c in allowed):
        raise ValueError("Invalid mix capability")
    result = []
    for mix in mixes:
        if not isinstance(mix, dict):
            raise ValueError("Invalid mix state")
        name = mix.get("mix")
        capability = next((c for c in allowed if c.get("mix") == name), None)
        if not capability or not opaque(name) or name in [m["mix"] for m in result]:
            raise ValueError("Mix lacks an advertised capability")
        level = mix.get("master_db")
        if level is not None and (
            type(level) not in (float, int)
            or not math.isfinite(level)
            or not -64 <= level <= 0
        ):
            raise ValueError("Invalid confirmed master level")
        routes, sources = capability.get("routes", []), capability.get("sources", [])
        if (
            not isinstance(routes, list)
            or len(routes) > 16
            or not all(opaque(r) for r in routes)
        ):
            raise ValueError("Invalid route capabilities")
        if (
            not isinstance(sources, list)
            or len(sources) > 32
            or not all(opaque(s) for s in sources)
        ):
            raise ValueError("Invalid source capabilities")
        channels = mix.get("channels", [])
        if not isinstance(channels, list) or len(channels) > 32:
            raise ValueError("Invalid channel collection")
        reduced = []
        for channel in channels:
            if not isinstance(channel, dict):
                raise ValueError("Invalid source state")
            if (
                channel.get("channel") not in sources
                or type(channel.get("mute")) is not bool
            ):
                raise ValueError("Invalid source mute state")
            source = channel["channel"]
            if source in [c["source"] for c in reduced]:
                raise ValueError("Duplicate source state")
            derived = channel.get("derived_level_db")
            pan = channel.get("derived_pan")
            if derived is not None and (
                type(derived) not in (int, float)
                or not math.isfinite(derived)
                or not -128 <= derived <= 20
            ):
                raise ValueError("Invalid confirmed channel level")
            if pan is not None and (
                type(pan) not in (int, float)
                or not math.isfinite(pan)
                or not 0 <= pan <= 1
            ):
                raise ValueError("Invalid confirmed channel pan")
            if any(
                type(channel.get(k)) is not bool
                for k in ("solo", "mono_included", "stereo_pair_included")
            ):
                raise ValueError("Invalid channel flags")
            reduced.append(
                {
                    "source": source,
                    "mute": channel["mute"],
                    "solo": channel["solo"],
                    "level_db": derived,
                    "pan": pan,
                    "included": channel["mono_included"]
                    or channel["stereo_pair_included"],
                }
            )
        route = mix.get("route")
        if route not in routes:
            raise ValueError("Unknown confirmed route")
        result.append(
            {
                "mix": name,
                "master_db": level,
                "route": route,
                "routes": routes,
                "channels": reduced,
            }
        )
    inputs = state.get("inputs", {}) if caps.get("switch_readback") is True else {}
    if inputs and (
        not isinstance(inputs, dict)
        or any(
            type(inputs.get(k)) is not bool for k in ("inst1", "inst2", "phantom_power")
        )
    ):
        raise ValueError("Invalid input indicators")
    return result, inputs


class Session:
    def __init__(self, app):
        self.app = app
        self.reader = self.writer = None
        self.requests = {}
        self.counter = 0
        self.epoch = None
        self.sequence = None
        self.features = []
        self.operation_id = None
        self.live = None
        self.task = None
        self.querying = False
        self.closed = False
        self.changed = asyncio.Event()
        self.record = None
        self.progress = time.monotonic()
        self.watching_meters = False

    async def run(self):
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(runtime_socket()), limit=MAX_FRAME - 2), 2
        )
        peer = self.writer.get_extra_info("socket")
        _, uid, _ = struct.unpack(
            "3i",
            peer.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
            ),
        )
        if uid != os.geteuid():
            raise ValueError("Unexpected service owner")
        reader = asyncio.create_task(self.receive())
        try:
            params = {"client": "omarchy-minifuse", "supported_api": [1]}
            if token := self.app.store.data.get("client_token"):
                params["client_token"] = token
            hello = await self.request("hello", params)
            if (
                type(hello.get("selected_api")) is not int
                or hello.get("selected_api") != 1
                or not opaque(hello.get("epoch"))
                or not opaque(hello.get("client_token"))
            ):
                raise ValueError("Incompatible service negotiation")
            self.epoch, self.features = hello["epoch"], hello.get("features", [])
            if not isinstance(self.features, list) or any(
                f not in self.features
                for f in (
                    "plans",
                    "subscriptions",
                    "durable_operations",
                    "live_controls",
                )
            ):
                raise ValueError("Service lacks required operation features")
            self.app.store.save(client_token=hello["client_token"])
            await self.subscribe()
            self.app.connected = True
            self.app.publish()
            while not reader.done():
                desired = self.app.visible and "signal_meters" in self.features
                if (
                    desired != self.watching_meters
                    and not self.live
                    and (not self.task or self.task.done())
                ):
                    raise SubscriptionRefresh()
                if self.app.meters and time.monotonic() - self.app.meter_time > 0.5:
                    self.app.meters = None
                    self.app.publish()
                if self.app.store.data.get("pending") and (
                    (not self.live and (not self.task or self.task.done()))
                    or time.monotonic() - self.progress > 10
                ):
                    await self.query()
                done, _ = await asyncio.wait({reader}, timeout=0.1)
                if reader in done:
                    await reader
            await reader
        finally:
            self.app.connected = False
            self.app.state = None
            self.app.meters = None
            if self.app.store.data.get("pending"):
                self.app.uncertain = True
            self.app.publish()
            self.closed = True
            reader.cancel()
            if self.task:
                self.task.cancel()
                await asyncio.gather(self.task, return_exceptions=True)
            await asyncio.gather(reader, return_exceptions=True)
            for _, future, _ in self.requests.values():
                if not future.done():
                    future.cancel()
            self.writer.close()
            with contextlib.suppress(OSError):
                await self.writer.wait_closed()

    async def subscribe(self):
        self.watching_meters = self.app.visible and "signal_meters" in self.features
        events = EVENTS + (["meters_updated"] if self.watching_meters else [])
        await self.request("subscribe", {"events": events}, self.baseline)

    async def request(self, method, params, callback=None):
        if self.closed or not self.writer or len(self.requests) >= 8:
            raise ConnectionError("Service request capacity unavailable")
        self.counter += 1
        identifier = "panel-" + str(self.counter)
        future = asyncio.get_running_loop().create_future()
        self.requests[identifier] = (method, future, callback)
        try:
            self.writer.write(
                encode({"api": 1, "id": identifier, "method": method, "params": params})
            )
            await asyncio.wait_for(self.writer.drain(), 2)
            return await asyncio.wait_for(future, 5)
        except asyncio.TimeoutError as error:
            self.writer.close()
            raise ConnectionError(
                "Service timed out; admitted changes will not be replayed"
            ) from error
        finally:
            self.requests.pop(identifier, None)

    async def receive(self):
        try:
            while True:
                first = await self.reader.readexactly(1)
                rest = (
                    b""
                    if first == b"\n"
                    else await asyncio.wait_for(self.reader.readuntil(b"\n"), 2)
                )
                value = decode((first + rest)[:-1])
                if "event" in value:
                    if (
                        not isinstance(value["event"], str)
                        or value.get("epoch") != self.epoch
                        or type(value.get("seq")) is not int
                        or self.sequence is None
                        or value["seq"] != self.sequence + 1
                        or not isinstance(value.get("data"), dict)
                    ):
                        raise ValueError("Subscription baseline or sequence changed")
                    self.sequence = value["seq"]
                    self.event(value["event"], value["data"])
                    continue
                if (
                    type(value.get("api")) is not int
                    or value["api"] != 1
                    or ("result" in value) == ("error" in value)
                ):
                    raise ValueError("Invalid response envelope")
                identifier = value.get("id")
                if not isinstance(identifier, str) or identifier not in self.requests:
                    raise ValueError("Unexpected response identity")
                _, future, callback = self.requests[identifier]
                if future.done():
                    raise ValueError("Duplicate response")
                if "error" in value:
                    if not isinstance(value["error"], dict):
                        raise ValueError("Invalid service error")
                    future.set_exception(ApiError(value["error"]))
                else:
                    if not isinstance(value["result"], dict):
                        raise ValueError("Invalid service result")
                    if callback:
                        callback(value["result"])
                    future.set_result(value["result"])
        finally:
            for _, future, _ in self.requests.values():
                if not future.done():
                    future.set_exception(
                        ConnectionError("Service disconnected; refresh required")
                    )

    def baseline(self, value):
        if (
            value.get("epoch") != self.epoch
            or type(value.get("seq")) is not int
            or value["seq"] < 0
        ):
            raise ValueError("Invalid subscription baseline")
        devices, states = value.get("devices"), value.get("states")
        if (
            not isinstance(devices, list)
            or len(devices) > 16
            or not isinstance(states, list)
            or len(states) > 16
        ):
            raise ValueError("Invalid device inventory")
        if any(
            not isinstance(d, dict) or not isinstance(d.get("capabilities", {}), dict)
            for d in devices
        ) or any(not isinstance(s, dict) for s in states):
            raise ValueError("Invalid inventory member")
        self.sequence = value["seq"]
        previous = self.app.state
        ready = [
            d
            for d in devices
            if d.get("connection") == "ready"
            and d.get("capabilities", {}).get("mixer") is True
        ]
        self.app.state = None
        if len(ready) == 1:
            candidate = next(
                (
                    s
                    for s in states
                    if s.get("device_id") == ready[0].get("device_id")
                    and s.get("generation") == ready[0].get("generation")
                ),
                None,
            )
            if candidate:
                state_view(candidate)
                if (
                    self.live
                    and previous
                    and (
                        candidate["generation"] != previous["generation"]
                        or candidate["revision"] != previous["revision"]
                    )
                ):
                    self.live["interrupted"] = True
                    self.live["latest"] = None
                    self.changed.set()
                    self.app.message = (
                        "Subscription state changed; the old gesture was stopped"
                    )
                self.app.state = candidate
        self.app.status = (
            "Confirmed device state"
            if self.app.state
            else "Device controls unavailable"
        )
        self.app.message = (
            self.app.message
            or "Inspect the current state before acknowledging the previous operation"
            if self.app.uncertain or (self.live and self.live["interrupted"])
            else ""
            if self.app.state
            else (
                "No interface connected"
                if not devices
                else "A supported, unambiguous MiniFuse mixer and matching module are required"
            )
        )

    def event(self, name, data):
        if name == "meters_updated":
            if not self.app.visible or not self.app.state:
                return
            if (data.get("device_id"), data.get("generation")) != (
                self.app.state["device_id"],
                self.app.state["generation"],
            ):
                return
            if data.get("available") is not True:
                self.app.meters = None
            else:
                sources, mixes = data.get("sources_dbfs"), data.get("mixes_dbfs")

                def valid(level):
                    return level is None or (
                        type(level) in (int, float)
                        and math.isfinite(level)
                        and -200 <= level <= 12
                    )

                if (
                    not isinstance(sources, list)
                    or len(sources) != 10
                    or not all(valid(v) for v in sources)
                    or not isinstance(mixes, list)
                    or len(mixes) != 3
                    or any(
                        not isinstance(pair, list)
                        or len(pair) != 2
                        or not all(valid(v) for v in pair)
                        for pair in mixes
                    )
                ):
                    raise ValueError("Invalid meter sample")
                if self.app.state["capabilities"].get("signal_meters") is not True:
                    return
                self.app.meters = {"sources": sources, "mixes": mixes}
                self.app.meter_time = time.monotonic()
            self.app.publish()
            return
        if name in ("device_added", "device_removed", "capabilities_changed"):
            raise ConnectionError("Device inventory changed; reading a fresh baseline")
        if (
            name == "state_changed"
            and self.app.state
            and data.get("device_id") == self.app.state["device_id"]
        ):
            if data.get("generation") != self.app.state["generation"]:
                raise ConnectionError("Device generation changed")
            state_view(data)
            if (
                self.live
                and data.get("operation_id") != self.operation_id
                and data.get("revision") != self.app.state["revision"]
            ):
                self.live["interrupted"] = True
                self.live["latest"] = None
                self.changed.set()
                self.app.message = "External state changed; the old gesture was stopped"
            self.app.state = data
            self.app.publish()
        elif (
            name in ("control_updated", "operation_finished")
            and data.get("operation_id") == self.operation_id
        ):
            self.record = data
            self.progress = time.monotonic()
            self.changed.set()
            if not self.live:
                self.complete(data)

    def identity(self):
        return {k: self.app.state[k] for k in ("device_id", "generation")}

    def retain(self, kind):
        key = secrets.token_hex(24)
        self.app.store.save(pending={"key": key, "kind": kind})
        self.operation_id = None
        self.record = None
        self.progress = time.monotonic()
        self.app.uncertain = False
        self.app.can_acknowledge = False
        self.app.message = ""
        return key

    def command(self, value):
        action = value.get("action")
        mix = self.app.mix()
        if action in ("master", "level", "pan"):
            level, finish = value.get("value"), value.get("finish")
            fields = {"action", "value", "finish"}
            if action != "master":
                fields.add("source")
            if set(value) != fields or type(finish) is not bool:
                raise ValueError("Invalid continuous control command")
            low, high = {"master": (-64, 0), "level": (-60, 12), "pan": (0, 1)}[action]
            if (level is None and action == "pan") or (
                level is not None
                and (
                    type(level) not in (int, float)
                    or not math.isfinite(level)
                    or not low <= level <= high
                )
            ):
                raise ValueError("Control value outside its supported range")
            if not self.app.writable() or not mix or mix["route"] != "mix":
                return
            target = {
                "kind": {
                    "master": "master_level",
                    "level": "channel_level",
                    "pan": "channel_pan",
                }[action],
                "mix": mix["mix"],
            }
            if action != "master":
                channel = next(
                    (c for c in mix["channels"] if c["source"] == value.get("source")),
                    None,
                )
                if not channel:
                    raise ValueError("Unsupported channel control")
                if not channel["included"]:
                    return
                target["source"] = channel["source"]
            if self.live:
                if self.live["target"] != target:
                    return
                if not self.live["ending"] and not self.live["interrupted"]:
                    self.live["latest"] = (level, finish)
                    self.live["ending"] = finish
                    self.changed.set()
                return
            if self.app.store.data.get("pending") or (
                self.task and not self.task.done()
            ):
                return
            self.live = {
                "target": target,
                "latest": (level, finish),
                "ending": finish,
                "interrupted": False,
            }
            self.task = asyncio.create_task(self.live_control())
            self.task.add_done_callback(self.task_done)
        elif action in ("route", "mute", "solo"):
            if (
                not self.app.writable()
                or not mix
                or self.app.store.data.get("pending")
                or (self.task and not self.task.done())
            ):
                return
            if action == "route":
                if (
                    set(value) != {"action", "value"}
                    or value.get("value") not in mix["routes"]
                ):
                    raise ValueError("Unsupported route")
                if value["value"] == mix["route"]:
                    return
                change = {"kind": "route", "mix": mix["mix"], "source": value["value"]}
            else:
                if (
                    set(value) != {"action", "source", "value"}
                    or type(value.get("value")) is not bool
                ):
                    raise ValueError("Invalid source switch command")
                channel = next(
                    (c for c in mix["channels"] if c["source"] == value.get("source")),
                    None,
                )
                if not channel:
                    raise ValueError("Source lacks a mute capability")
                if channel[action] == value["value"]:
                    return
                change = {
                    "kind": "channel",
                    "mix": mix["mix"],
                    "source": channel["source"],
                    action: value["value"],
                }
            self.task = asyncio.create_task(self.change(change))
            self.task.add_done_callback(self.task_done)
        self.app.publish()

    def task_done(self, task):
        if not task.cancelled() and task.exception():
            self.failed(task.exception())
        self.app.publish()

    async def change(self, change):
        try:
            result = await self.request(
                "plan_changes",
                {
                    **self.identity(),
                    "expected_revision": self.app.state["revision"],
                    "changes": [change],
                },
            )
            key = self.retain("plan")
            self.app.publish()
            accepted = await self.request(
                "apply_plan", {"plan_id": result["plan_id"], "idempotency_key": key}
            )
            if not opaque(accepted.get("operation_id")):
                raise ValueError("Invalid admitted operation identity")
            self.operation_id = accepted["operation_id"]
            await self.query()
        except (ApiError, OSError, ValueError) as error:
            self.failed(error)
        finally:
            self.app.publish()

    async def live_control(self):
        try:
            key = self.retain("live_control")
            accepted = await self.request(
                "begin_control",
                {
                    **self.identity(),
                    "expected_revision": self.app.state["revision"],
                    "target": self.live["target"],
                    "idempotency_key": key,
                },
            )
            if not opaque(accepted.get("operation_id")):
                raise ValueError("Invalid admitted operation identity")
            self.operation_id = accepted["operation_id"]
            if accepted.get("status") != "pending":
                self.complete(accepted)
                return
            sequence = 0
            last_sent = 0
            while self.live:
                if self.live["interrupted"]:
                    result = await self.request(
                        "cancel_control", {"operation_id": self.operation_id}
                    )
                    self.complete(result)
                    break
                if self.live["latest"] is None:
                    self.changed.clear()
                    await asyncio.wait_for(self.changed.wait(), 10)
                    continue
                await asyncio.sleep(max(0, 0.08 - (time.monotonic() - last_sent)))
                if self.live["interrupted"] or self.live["latest"] is None:
                    continue
                value, finish = self.live["latest"]
                self.live["latest"] = None
                sequence += 1
                if sequence > 512:
                    raise ValueError(
                        "Gesture sample limit reached; release and review the confirmed level"
                    )
                self.record = None
                self.changed.clear()
                await self.request(
                    "update_control",
                    {
                        "operation_id": self.operation_id,
                        "sequence": sequence,
                        "value": value,
                        "finish": finish,
                    },
                )
                last_sent = time.monotonic()
                deadline = time.monotonic() + 10
                while self.record is None or (
                    self.record.get("status") == "pending"
                    and self.record.get("sample_sequence", 0) < sequence
                ):
                    self.changed.clear()
                    await asyncio.wait_for(
                        self.changed.wait(), max(0.001, deadline - time.monotonic())
                    )
                record = self.record
                if record.get("status") != "pending":
                    self.complete(record)
                    break
                if (
                    record.get("sample_sequence") != sequence
                    or record.get("device_outcome") != "verified"
                ):
                    raise ValueError(
                        "Control verification changed; inspect the confirmed state"
                    )
        except (ApiError, OSError, ValueError, asyncio.TimeoutError) as error:
            self.failed(error)
        finally:
            self.live = None
            self.app.publish()

    def failed(self, error):
        self.app.message = (
            str(error)[:240]
            or "Control verification timed out; no movement will be replayed"
        )
        self.live = None
        if self.app.store.data.get("pending"):
            if (
                isinstance(error, ApiError)
                and self.operation_id is None
                and error.error.get("details", {}).get("device_write_attempted")
                is False
            ):
                self.app.store.resolve({"error": error.error})
            else:
                self.app.uncertain = True
        self.app.publish()

    async def query(self):
        if self.querying or not self.app.store.data.get("pending"):
            return
        self.querying = True
        try:
            result = await self.request(
                "get_operation",
                {"idempotency_key": self.app.store.data["pending"]["key"]},
            )
            if self.operation_id is not None and self.operation_id != result.get(
                "operation_id"
            ):
                raise ValueError("Retained operation result identity changed")
            self.operation_id = result.get("operation_id")
            self.complete(result)
        except ApiError as error:
            self.app.uncertain = True
            self.app.can_acknowledge = error.error.get("code") == "outcome_unknown"
            self.app.message = str(error)
            self.app.publish()
        finally:
            self.querying = False

    def complete(self, result):
        if result.get("status") not in (
            "pending",
            "completed",
            "indeterminate",
        ) or not opaque(result.get("operation_id")):
            raise ValueError("Invalid operation record")
        if (
            self.operation_id is not None
            and result["operation_id"] != self.operation_id
        ):
            raise ValueError("Operation result identity changed")
        if not self.app.store.data.get("pending"):
            return
        if result.get("status") == "pending":
            self.app.can_acknowledge = False
            return
        self.record = result
        if (
            result.get("status") == "indeterminate"
            or result.get("device_outcome") == "unknown"
        ):
            self.app.uncertain = True
            self.app.can_acknowledge = True
            self.app.message = "Outcome uncertain. Inspect current state before acknowledging; no write will be replayed."
        else:
            self.app.store.resolve(result)
            self.app.uncertain = False
            self.app.can_acknowledge = False
            self.app.message = (
                "Device readback verified"
                if result.get("device_outcome") == "verified"
                else "Operation ended; inspect current device state"
            )
            if result.get("journal_status") == "failed":
                self.app.message = "Device result known; service journal finalization failed. Retain the archived operation reference."
            if result.get("gesture_end") not in (None, "finished"):
                self.app.message = (
                    "Gesture ended ("
                    + str(result["gesture_end"])
                    + "); confirmed changes retained"
                )
        self.app.publish()


class Application:
    def __init__(self, store):
        self.store = store
        self.session = None
        self.connected = False
        self.state = None
        self.selected = "out12"
        self.status = "Connecting to mf-service"
        self.message = ""
        self.uncertain = bool(store.data.get("pending"))
        self.can_acknowledge = False
        self.output = asyncio.Queue(maxsize=1)
        self.launches = set()
        self.applications = set()
        self.visible = False
        self.meters = None
        self.meter_time = 0

    def mix(self):
        if not self.state:
            return None
        mixes, _ = state_view(self.state)
        return next((m for m in mixes if m["mix"] == self.selected), None)

    def writable(self):
        return (
            self.connected
            and self.state is not None
            and not self.uncertain
            and self.state.get("capabilities", {}).get("mixer") is True
        )

    def publish(self):
        mixes, inputs = state_view(self.state) if self.state else ([], {})
        if mixes and self.selected not in [m["mix"] for m in mixes]:
            self.selected = mixes[0]["mix"]
        live = bool(self.session and self.session.live)
        task = self.session.task if self.session else None
        busy = bool(self.store.data.get("pending") or (task and not task.done()))
        value = {
            "status": self.status,
            "message": self.message,
            "connected": self.connected,
            "can_write": self.writable(),
            "busy": busy,
            "live": live,
            "live_target": self.session.live["target"] if live else None,
            "meters": self.meters
            if self.visible and time.monotonic() - self.meter_time <= 0.5
            else None,
            "uncertain": self.uncertain,
            "can_acknowledge": self.can_acknowledge,
            "selected": self.selected,
            "mixes": mixes,
            "inputs": inputs,
            "operation_id": self.session.operation_id if self.session else None,
        }
        raw = encode(value, MAX_VIEW)
        if self.output.full():
            self.output.get_nowait()
        self.output.put_nowait(raw)

    def command(self, value):
        action = value.get("action")
        if (
            action == "watch"
            and set(value) == {"action", "value"}
            and type(value["value"]) is bool
        ):
            self.visible = value["value"]
            if not self.visible:
                self.meters = None
        elif action == "select_mix" and set(value) == {"action", "value"}:
            mixes, _ = state_view(self.state) if self.state else ([], {})
            if not self.store.data.get("pending") and value["value"] in [
                m["mix"] for m in mixes
            ]:
                self.selected = value["value"]
        elif action == "acknowledge" and set(value) == {"action"}:
            if (
                self.connected
                and self.state
                and self.uncertain
                and self.can_acknowledge
                and self.store.data.get("pending")
            ):
                self.store.resolve(
                    self.session.record or {"outcome": "unavailable"}, acknowledged=True
                )
                self.uncertain = False
                self.can_acknowledge = False
                self.message = "Current state acknowledged; prior evidence archived without retrying the operation"
        elif action == "open_app" and set(value) == {"action"}:
            if not self.launches:
                task = asyncio.create_task(self.open_app())
                self.launches.add(task)
                task.add_done_callback(self.launches.discard)
        elif (
            action in ("master", "level", "pan", "route", "mute", "solo")
            and self.session
        ):
            self.session.command(value)
        else:
            raise ValueError("Unsupported panel command")
        self.publish()

    async def open_app(self):
        # A detached application must outlive helper unload. Asyncio subprocess
        # transports can terminate children when their owning loop is closed.
        self.applications = {
            process for process in self.applications if process.poll() is None
        }
        if len(self.applications) >= 4:
            self.message = "Application launch is already in progress"
            self.publish()
            return
        try:
            process = subprocess.Popen(
                ["minifuse-control"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                code = await asyncio.to_thread(process.wait, timeout=0.25)
                if code:
                    raise OSError("MiniFuse Control could not start")
            except subprocess.TimeoutExpired:
                self.applications.add(process)
                return
        except OSError:
            self.message = "Install MiniFuse Control and make minifuse-control available in the session PATH"
        self.publish()

    async def connect(self):
        while True:
            self.session = Session(self)
            refreshing = False
            try:
                await self.session.run()
            except SubscriptionRefresh:
                refreshing = True
            except (
                OSError,
                ValueError,
                ApiError,
                asyncio.IncompleteReadError,
                asyncio.LimitOverrunError,
                asyncio.TimeoutError,
            ) as error:
                self.message = str(error)[:240]
            finally:
                if self.session.writer:
                    self.session.writer.close()
                self.connected = False
                self.state = None
                self.status = (
                    "Refreshing signal meters" if refreshing else "Service unavailable"
                )
                self.can_acknowledge = False
                if self.store.data.get("pending"):
                    self.uncertain = True
                self.publish()
            if not refreshing:
                await asyncio.sleep(2)

    async def commands(self):
        reader = asyncio.StreamReader(limit=MAX_COMMAND)
        protocol = asyncio.StreamReaderProtocol(reader)
        transport, _ = await asyncio.get_running_loop().connect_read_pipe(
            lambda: protocol, sys.stdin.buffer
        )
        try:
            while True:
                try:
                    raw = await reader.readuntil(b"\n")
                except asyncio.IncompleteReadError:
                    return
                try:
                    self.command(decode(raw[:-1], MAX_COMMAND))
                except (ValueError, OSError) as error:
                    self.message = str(error)[:240]
                    self.publish()
        finally:
            transport.close()

    async def output_loop(self):
        while True:
            raw = await self.output.get()

            def write():
                sys.stdout.buffer.write(raw)
                sys.stdout.buffer.flush()

            await asyncio.to_thread(write)


async def run():
    store = Store()
    app = Application(store)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop.set)
    app.publish()
    tasks = [
        asyncio.create_task(coro)
        for coro in (app.connect(), app.commands(), app.output_loop(), stop.wait())
    ]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        store.close()


def main():
    parser = argparse.ArgumentParser(
        description="MiniFuse Omarchy plugin client bridge"
    )
    parser.add_argument("--version", action="version", version="0.1.0-dev")
    parser.parse_args()
    try:
        asyncio.run(run())
    except (OSError, ValueError, asyncio.LimitOverrunError) as error:
        print(
            "MiniFuse plugin client unavailable: " + str(error)[:240], file=sys.stderr
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
