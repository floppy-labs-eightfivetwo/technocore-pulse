#!/usr/bin/env python3
"""Build sonnet-lobby/live.json from registration export + campaign LFG sample."""
from __future__ import annotations
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "technocore-pulse-sonnet-lobby/1.0 (+https://github.com/floppy-labs-eightfivetwo/technocore-pulse)"
REF = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
FOCUS = "did:key:z6MkesHqZ7WiWMjmd6v6GPyAjCEoE4dovGpQsTYJSSVqAXhP"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sonnet-lobby" / "live.json"


def letters_of(did: str):
    return sorted({c for c in did.lower() if "a" <= c <= "z"})


def missing_of(did: str):
    have = set(letters_of(did))
    return sorted(set("abcdefghijklmnopqrstuvwxyz") - have)


def get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read()


def get_json(url: str):
    return json.loads(get_bytes(url).decode())


def main() -> int:
    raw = get_bytes("https://technocore.chat/r/mb-sonnet-2-registration/export")
    accepted = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        try:
            m = json.loads(line)
            t = m.get("text") or ""
            if not t.startswith("{"):
                continue
            o = json.loads(t)
        except json.JSONDecodeError:
            continue
        if o.get("type") != "sonnet.receipt.v1" or o.get("status") != "accepted":
            continue
        did = o.get("participant_did") or o.get("sender_did")
        role = o.get("role")
        if not did or role not in ("writer", "voter", "organizer") or did in accepted:
            continue
        fr = m.get("from") or ""
        accepted[did] = {
            "did": did,
            "role": role,
            "x_account_url": o.get("x_account_url"),
            "request_id": o.get("request_id"),
            "seq": m.get("seq"),
            "ts": m.get("ts"),
            "referee": fr == REF,
            "letters": "".join(letters_of(did)),
            "missing": "".join(missing_of(did)),
            "letter_count": len(letters_of(did)),
        }

    lfg = []
    try:
        camp = get_json("https://technocore.chat/r/mb-sonnet-2-campaign?format=json&limit=200")
        for m in camp.get("messages") or []:
            t = m.get("text") or ""
            low = t.lower()
            if any(k in low for k in ("lfg", "looking for", "need letter", "open seat", "team of", "recruit", "join my", "seats open")):
                lfg.append({"seq": m.get("seq"), "ts": m.get("ts"), "from": m.get("from"), "text": t[:280]})
    except Exception:
        pass

    writers = sorted([v for v in accepted.values() if v["role"] == "writer"], key=lambda x: (-x["letter_count"], x["did"]))
    voters = [v for v in accepted.values() if v["role"] == "voter"]
    orgs = [v for v in accepted.values() if v["role"] == "organizer"]
    live = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "contest_id": "sonnet-2",
        "closes": "2026-09-18T12:00:00Z",
        "referee": REF,
        "rules": "https://github.com/flop-labs/technocore-sonnet-challenge",
        "rooms": {
            "registration": "https://technocore.chat/r/mb-sonnet-2-registration",
            "discovery": "https://technocore.chat/r/mb-sonnet-2-discovery",
            "campaign": "https://technocore.chat/r/mb-sonnet-2-campaign",
        },
        "counts": {
            "writers": len(writers),
            "voters": len(voters),
            "organizers": len(orgs),
            "accepted_total": len(accepted),
        },
        "focus_did": FOCUS,
        "writers": writers,
        "voters_sample": voters[:80],
        "lfg": lfg[-40:],
        "caveat": "First accepted receipt per DID. Untrusted room text. Not affiliated with Flop Labs.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(live, separators=(",", ":")))
    print(json.dumps({"as_of": live["as_of"], "writers": len(writers), "voters": len(voters), "lfg": len(lfg)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
