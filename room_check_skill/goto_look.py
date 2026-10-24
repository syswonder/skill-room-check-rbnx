"""Go somewhere through Scene and navigation, then photograph it.

Every move goes through `robonix/service/navigation/navigate`, which plans
around obstacles; this module never drives the chassis itself.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import math
import time
from typing import Any

from fastmcp import Client

NEEDS = {
    "goal_region": "robonix/system/scene/goal_region",
    "goal_near": "robonix/system/scene/goal_near",
    "navigate": "robonix/service/navigation/navigate",
    "status": "robonix/service/navigation/navigate/status",
    "snapshot": "robonix/primitive/camera/snapshot",
}
TERMINAL = {"SUCCEEDED", "FAILED", "CANCELED", "TIMEOUT"}


class GoLook:
    def __init__(self, endpoints: dict[str, str], nav_timeout_s: float, save_dir: str = "") -> None:
        self.endpoints = endpoints
        self.nav_timeout_s = nav_timeout_s
        self.save_dir = save_dir

    def call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        async def once() -> dict[str, Any]:
            async with Client(self.endpoints[tool]) as client:
                result = await client.call_tool(tool, args)
                return json.loads(result.content[0].text) if result.content else {}

        return asyncio.run(once())

    def visit(self, goal_tool: str, key: str, target: str, sweep: bool) -> tuple[bool, str, str]:
        """Resolve `target` with a Scene goal tool, drive there and photograph it.

        With `sweep`, turn to four headings 90 degrees apart (each turn is a
        navigation goal at the same position) and return the four photos as
        one labelled 2x2 sheet; else one photo at the goal heading.
        Returns (arrived, jpeg base64 or "", detail).
        """
        goal = self.call(goal_tool, {key: target})
        if not goal.get("reachable"):
            return False, "", f"no reachable pose for {target!r}: {goal.get('reason', '')}"
        x, y, yaw = float(goal["x"]), float(goal["y"]), float(goal["yaw"])
        ok, why = self._drive(x, y, yaw)
        if not ok:
            return False, "", f"navigation to {target!r} at ({x:.2f}, {y:.2f}) did not finish: {why}"
        if not sweep:
            jpeg = self._snapshot()
            if jpeg:
                self._save(target, jpeg)
            return True, base64.b64encode(jpeg).decode() if jpeg else "", f"arrived at {target!r}; one photo at the goal heading"
        shots = []
        for k in range(4):
            if k and not self._drive(x, y, yaw + k * math.pi / 2)[0]:
                break
            shots.append(self._snapshot())
        shots = [s for s in shots if s]
        if not shots:
            return True, "", f"arrived at {target!r} but the camera returned no JPEG"
        detail = (f"arrived at {target!r}; {len(shots)} photos turning left 90 degrees each time, "
                  "labelled #1 (first heading) to #4 in the sheet, left to right, top to bottom")
        jpeg = sheet(shots)
        self._save(target, jpeg)
        return True, base64.b64encode(jpeg).decode(), detail

    def _save(self, target: str, jpeg: bytes) -> None:
        if self.save_dir:
            from pathlib import Path

            path = Path(self.save_dir) / f"{time.strftime('%Y%m%d-%H%M%S')}-{target.replace('/', '_')}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(jpeg)

    def _snapshot(self) -> bytes:
        shot = self.call("snapshot", {})
        if str(shot.get("encoding", "")).lower() != "jpeg" or not shot.get("data"):
            return b""
        return base64.b64decode(shot["data"])

    def _drive(self, x: float, y: float, yaw: float) -> tuple[bool, str]:
        goal = {
            "header": {"frame_id": "map", "stamp": {"sec": 0, "nanosec": 0}},
            "pose": {
                "position": {"x": x, "y": y, "z": 0.0},
                "orientation": {"x": 0.0, "y": 0.0, "z": math.sin(yaw / 2), "w": math.cos(yaw / 2)},
            },
        }
        sent = self.call("navigate", {"goal": goal})
        if not sent.get("accepted"):
            return False, f"goal rejected: {sent.get('detail', '')}"
        deadline = time.monotonic() + self.nav_timeout_s
        while time.monotonic() < deadline:
            state = str(self.call("status", {"run_id": sent.get("run_id", "")}).get("state", "")).upper()
            if state in TERMINAL:
                return state == "SUCCEEDED", state
            time.sleep(1.0)
        return False, f"no result within {self.nav_timeout_s:.0f} s"


def sheet(jpegs: list[bytes]) -> bytes:
    """Up to four photos as one 2x2 JPEG, each labelled #1..#4."""
    from PIL import Image, ImageDraw

    tiles = [Image.open(io.BytesIO(j)).convert("RGB").resize((480, 360)) for j in jpegs]
    out = Image.new("RGB", (960, 720), "white")
    draw = ImageDraw.Draw(out)
    for i, tile in enumerate(tiles):
        x, y = (i % 2) * 480, (i // 2) * 360
        out.paste(tile, (x, y))
        draw.rectangle((x + 8, y + 8, x + 52, y + 40), fill="black")
        draw.text((x + 16, y + 16), f"#{i + 1}", fill="white")
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=85)
    return buf.getvalue()
