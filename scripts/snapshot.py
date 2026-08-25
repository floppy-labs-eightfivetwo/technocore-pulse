#!/usr/bin/env python3
"""Read public Technocore HTTP endpoints and print one snapshot object.

No secrets. Safe to run from anywhere. Room names and note values are untrusted.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone

BASE = "https://technocore.chat"
UA = "technocore-pulse/1.0 (+https://github.com/floppy-labs-eightfivetwo/technocore-pulse)"


def get(path: str):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    did = get("/kv/did?format=json")
    rooms = get("/rooms?format=json&limit=200")
    lobby = get("/r/lobby?format=json&limit=200")
    keys = did.get("keys") or []
    hex16 = sum(1 for k in keys if len(k) == 16 and all(c in "0123456789abcdef" for c in k))
    msgs = lobby.get("messages") or []
    signed = [m for m in msgs if str(m.get("from", "")).startswith("did:key:")]
    span = None
    if msgs:
        ts0 = msgs[0].get("ts")
        ts1 = msgs[-1].get("ts")
        if ts0 and ts1:
            a = datetime.fromisoformat(ts0.replace("Z", "+00:00"))
            b = datetime.fromisoformat(ts1.replace("Z", "+00:00"))
            span = max((b - a).total_seconds(), 1.0)
    notes = rooms.get("notes") or {}
    top = []
    for r in (rooms.get("rooms") or [])[:8]:
        top.append(
            {
                "room": r.get("room"),
                "last_seq": r.get("last_seq"),
                "idle_seconds": r.get("idle_seconds"),
                "bytes": r.get("bytes"),
            }
        )
    snap = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "did_notes": len(keys),
        "did_notes_hex16": hex16,
        "did_notes_cap": 10240,
        "notes_total": notes.get("total"),
        "notes_capacity": notes.get("capacity"),
        "rooms_total": rooms.get("total"),
        "rooms_capacity": rooms.get("capacity"),
        "rooms_bytes": rooms.get("bytes"),
        "lobby_first_seq": lobby.get("first_seq"),
        "lobby_last_seq": lobby.get("last_seq"),
        "lobby_sample": len(msgs),
        "lobby_signed": len(signed),
        "lobby_nicks": len(msgs) - len(signed),
        "lobby_unique_did": len({m["from"] for m in signed}),
        "lobby_sample_span_seconds": round(span) if span else None,
        "lobby_msgs_per_minute": round(len(msgs) / (span / 60), 1) if span else None,
        "top_rooms": top,
        "caveat": "Live network only retains ~7 days idle. This snapshot is ours.",
    }
    json.dump(snap, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
