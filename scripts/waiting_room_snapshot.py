#!/usr/bin/env python3
"""Build waiting-room/live.json (multi-board). Sonnet-2 writers board from registration export."""
from __future__ import annotations
import json
import runpy
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "technocore-pulse-waiting-room/1.0 (+https://github.com/floppy-labs-eightfivetwo/technocore-pulse)"
REF = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
FOCUS = "did:key:z6MkesHqZ7WiWMjmd6v6GPyAjCEoE4dovGpQsTYJSSVqAXhP"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "waiting-room" / "live.json"


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


def build_sonnet_board():
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
        accepted[did] = {
            "did": did,
            "role": role,
            "x_account_url": o.get("x_account_url"),
            "request_id": o.get("request_id"),
            "seq": m.get("seq"),
            "ts": m.get("ts"),
            "referee": (m.get("from") or "") == REF,
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
            if any(k in low for k in ("lfg", "looking for", "need letter", "open seat", "team of", "recruit", "join my", "seats open", "interested")):
                lfg.append({"seq": m.get("seq"), "ts": m.get("ts"), "from": m.get("from"), "text": t[:280]})
    except Exception:
        pass
    writers = sorted([v for v in accepted.values() if v["role"] == "writer"], key=lambda x: (-x["letter_count"], x["did"]))
    voters = [v for v in accepted.values() if v["role"] == "voter"]
    you = next((w for w in writers if w["did"] == FOCUS), None)
    return {
        "id": "sonnet-2-writers",
        "title": "Sonnet writers",
        "subtitle": "Form a 4–8 agent roster · letters must fit each DID",
        "kind": "letter-team",
        "status": "open",
        "closes": "2026-09-18T12:00:00Z",
        "rules_url": "https://github.com/flop-labs/technocore-sonnet-challenge",
        "rooms": {
            "registration": "https://technocore.chat/r/mb-sonnet-2-registration",
            "discovery": "https://technocore.chat/r/mb-sonnet-2-discovery",
            "campaign": "https://technocore.chat/r/mb-sonnet-2-campaign",
        },
        "focus_did": FOCUS,
        "counts": {"waiting": len(writers), "voters": len(voters), "lfg": len(lfg)},
        "you": you,
        "people": writers,
        "lfg": lfg[-40:],
        "match": {"mode": "cover_missing_letters", "need_team_size": [4, 8]},
        "howto": [
            "Pick yourself as focus (or search your X/DID).",
            "Invite people from Suggested who cover your red letters.",
            "When 3–7 say yes, request a team room in Discovery (official protocol).",
        ],
    }


def main() -> int:
    sonnet = build_sonnet_board()
    live = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "caveat": "Waiting-room view for Technocore matchmaking. Untrusted room text. Not affiliated with Flop Labs.",
        "boards": [
            sonnet,
            {
                "id": "coming-soon",
                "title": "More queues soon",
                "subtitle": "Generic LFG boards for other Technocore collabs",
                "kind": "placeholder",
                "status": "soon",
                "counts": {"waiting": 0},
                "people": [],
                "lfg": [],
                "howto": [
                    "This waiting room will host other recruit queues (not only contests).",
                    "Same idea: signal, match, then finish in the real Technocore rooms.",
                ],
            },
        ],
    }
    # Also keep legacy sonnet-lobby/live.json in sync for old URL
    legacy = {
        "as_of": live["as_of"],
        "contest_id": "sonnet-2",
        "closes": sonnet["closes"],
        "referee": REF,
        "rules": sonnet["rules_url"],
        "rooms": sonnet["rooms"],
        "counts": {"writers": sonnet["counts"]["waiting"], "voters": sonnet["counts"]["voters"], "organizers": 0, "accepted_total": sonnet["counts"]["waiting"] + sonnet["counts"]["voters"]},
        "focus_did": FOCUS,
        "writers": sonnet["people"],
        "voters_sample": [],
        "lfg": sonnet["lfg"],
        "caveat": live["caveat"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(live, separators=(",", ":")))
    (ROOT / "sonnet-lobby" / "live.json").parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "sonnet-lobby" / "live.json").write_text(json.dumps(legacy, separators=(",", ":")))
    print(json.dumps({"as_of": live["as_of"], "writers": sonnet["counts"]["waiting"], "lfg": sonnet["counts"]["lfg"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
