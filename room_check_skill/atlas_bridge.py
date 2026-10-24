"""Atlas registration and the MCP entrypoint of the room-check skill."""
from __future__ import annotations

import asyncio
import logging
import time

from robonix_api import ATLAS, Err, Ok, Skill

from room_check_mcp import VisitRegion_Request, VisitRegion_Response

from .goto_look import NEEDS, GoLook

logging.basicConfig(level=logging.INFO, format="[room-check] %(levelname)s %(message)s")
log = logging.getLogger("room_check")

skill = Skill(id="room_check", namespace="robonix/skill/room_check")
config: dict = {}
go: GoLook | None = None


def resolve(deadline_s: float = 45.0) -> dict[str, str]:
    """MCP endpoints of everything in NEEDS, found through Atlas."""
    found: dict[str, str] = {}
    deadline = time.monotonic() + deadline_s
    while time.monotonic() < deadline and len(found) < len(NEEDS):
        for tool, contract in NEEDS.items():
            if tool in found:
                continue
            try:
                view = ATLAS.find_unique_capability(contract_id=contract, transport="mcp")
                channel = skill.connect_capability(view, contract, "mcp")
                if channel.endpoint:
                    found[tool] = channel.endpoint
                channel.close()
            except Exception:  # noqa: BLE001
                continue
        time.sleep(1.0)
    missing = [NEEDS[t] for t in NEEDS if t not in found]
    if missing:
        raise RuntimeError(f"missing Atlas dependencies: {missing}")
    return found


@skill.mcp("robonix/skill/room_check/visit")
async def visit(req: VisitRegion_Request) -> VisitRegion_Response:
    """Drive to one region and photograph it."""
    if go is None:
        raise RuntimeError("room-check is not active")
    arrived, image, detail = await asyncio.to_thread(go.visit, "goal_region", "region_id", req.region.strip(), True)
    log.info("visit %s: %s", req.region, detail)
    return VisitRegion_Response(arrived=arrived, image_base64=image, format="jpeg" if image else "", detail=detail)


@skill.on_init
def init(cfg: dict):
    global config
    config = dict(cfg or {})
    if float(config.get("nav_timeout_s", 180)) <= 0:
        return Err("nav_timeout_s must be greater than zero")
    return Ok()


@skill.on_activate
def activate():
    global go
    if go is not None:
        return Ok()
    try:
        go = GoLook(resolve(), float(config.get("nav_timeout_s", 180)), str(config.get("save_dir", "")))
    except Exception as exc:  # noqa: BLE001
        return Err(str(exc))
    return Ok()


@skill.on_deactivate
def deactivate():
    global go
    go = None
    return Ok()


if __name__ == "__main__":
    skill.run()
