#!/usr/bin/env python3
"""Read public /r/kibble and write kibble/live.json for the useful-work radar."""
from __future__ import annotations
import json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://technocore.chat"
UA = "technocore-pulse-kibble/1.0 (+https://github.com/floppy-labs-eightfivetwo/technocore-pulse)"
OUT = Path(__file__).resolve().parents[1] / "kibble" / "live.json"


def get(path: str):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    d = get("/r/kibble?format=json&limit=200")
    msgs = []
    for m in d.get("messages") or []:
        msgs.append({
            "seq": m.get("seq"),
            "ts": m.get("ts"),
            "from": m.get("from"),
            "text": (m.get("text") or "")[:400],
            "nonce": m.get("nonce"),
        })
    live = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": BASE + "/r/kibble?format=json&limit=200",
        "room": d.get("room"),
        "first_seq": d.get("first_seq"),
        "last_seq": d.get("last_seq"),
        "count": len(msgs),
        "messages": msgs,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(live, separators=(",", ":")))
    print(json.dumps({"as_of": live["as_of"], "count": live["count"], "last_seq": live["last_seq"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
