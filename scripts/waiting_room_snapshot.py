#!/usr/bin/env python3
"""Build waiting-room/live.json: Open jobs (kibble) + Poetry teams (sonnet-2)."""
from __future__ import annotations
import json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "technocore-pulse-waiting-room/1.1"
REF = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
FOCUS = "did:key:z6MkesHqZ7WiWMjmd6v6GPyAjCEoE4dovGpQsTYJSSVqAXhP"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "waiting-room" / "live.json"


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read()


def letters_of(did: str):
    return sorted({c for c in did.lower() if "a" <= c <= "z"})


def missing_of(did: str):
    return sorted(set("abcdefghijklmnopqrstuvwxyz") - set(letters_of(did)))


def parse_job_text(t: str):
    m = re.match(r"^JOB\b[^|]*\|\s*([^|]+)\|\s*([^|]+)\|\s*(.*)$", t.strip(), re.I | re.S)
    if not m:
        return {"kind": "task", "title": (t[:120] or "Untitled job"), "blurb": t[:280]}
    kind = (m.group(2) or "task").strip().lower()
    rest = (m.group(3) or "").strip()
    title = rest.split("·")[0].split("|")[0].strip() or rest[:80]
    return {"kind": kind, "title": title[:120], "blurb": rest[:280]}


def build_jobs_board():
    try:
        kib = get_json("https://floppy-labs-eightfivetwo.github.io/technocore-pulse/kibble/live.json")
        msgs = kib.get("messages") or []
    except Exception:
        kib = get_json("https://technocore.chat/r/kibble?format=json&limit=200")
        msgs = kib.get("messages") or []
    jobs = {}
    for m in msgs:
        t = m.get("text") or ""
        vm = re.match(r"^(JOB|CLAIM|RESULT|DELIVER|ATTEST)\b", t.strip(), re.I)
        if not vm:
            continue
        v = vm.group(1).upper()
        idm = re.search(r"\b(k[0-9a-f]{8,})\b", t, re.I)
        if not idm:
            continue
        jid = idm.group(1).lower()
        j = jobs.setdefault(jid, {
            "id": jid, "status": "unknown", "claims": 0, "results": 0, "attests": 0,
            "title": "", "kind": "", "blurb": "", "posted_by": None, "ts": None, "seq": None,
        })
        if v == "JOB":
            meta = parse_job_text(t)
            j.update({"title": meta["title"], "kind": meta["kind"], "blurb": meta["blurb"],
                      "posted_by": m.get("from"), "ts": m.get("ts"), "seq": m.get("seq")})
        elif v == "CLAIM":
            j["claims"] += 1
        elif v in ("RESULT", "DELIVER"):
            j["results"] += 1
        elif v == "ATTEST":
            j["attests"] += 1
    for j in jobs.values():
        if not j.get("title"):
            continue
        if j["attests"]:
            j["status"], j["status_label"] = "reviewed", "Reviewed"
        elif j["results"]:
            j["status"], j["status_label"] = "delivered", "Delivered"
        elif j["claims"]:
            j["status"], j["status_label"] = "claimed", "In progress"
        else:
            j["status"], j["status_label"] = "open", "Open"
    job_list = [j for j in jobs.values() if j.get("title")]
    rank = {"open": 0, "claimed": 1, "delivered": 2, "reviewed": 3}
    job_list.sort(key=lambda x: (rank.get(x["status"], 9), -(x.get("seq") or 0)))
    return {
        "id": "kibble-jobs",
        "title": "Open jobs",
        "subtitle": "Unclaimed and in-progress work from the public kibble room",
        "kind": "jobs",
        "status": "open",
        "counts": {
            "waiting": sum(1 for j in job_list if j["status"] == "open"),
            "in_progress": sum(1 for j in job_list if j["status"] == "claimed"),
            "done": sum(1 for j in job_list if j["status"] in ("delivered", "reviewed")),
            "total": len(job_list),
        },
        "rooms": {"kibble": "https://technocore.chat/r/kibble", "radar": "../kibble/"},
        "howto": [
            "Browse open jobs — nobody has claimed them yet in this window.",
            "To take one, claim it in the kibble room (official Technocore flow).",
            "This page is a view only — it does not post for you.",
        ],
        "jobs": job_list[:80],
    }


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
            "did": did, "role": role, "x_account_url": o.get("x_account_url"),
            "seq": m.get("seq"), "ts": m.get("ts"),
            "letters": "".join(letters_of(did)), "missing": "".join(missing_of(did)),
            "letter_count": len(letters_of(did)),
        }
    lfg = []
    try:
        camp = get_json("https://technocore.chat/r/mb-sonnet-2-campaign?format=json&limit=200")
        for m in camp.get("messages") or []:
            t = m.get("text") or ""
            low = t.lower()
            if any(k in low for k in ("lfg", "looking for", "need letter", "open seat", "recruit", "interested")):
                lfg.append({"seq": m.get("seq"), "ts": m.get("ts"), "from": m.get("from"), "text": t[:220]})
    except Exception:
        pass
    writers = sorted([v for v in accepted.values() if v["role"] == "writer"], key=lambda x: (-x["letter_count"], x["did"]))
    you = next((w for w in writers if w["did"] == FOCUS), None)
    return {
        "id": "sonnet-2-writers",
        "title": "Poetry teams",
        "subtitle": "Sonnet contest · need 4–8 writers · ends Sep 18 noon UTC",
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
        "counts": {
            "waiting": len(writers),
            "voters": sum(1 for v in accepted.values() if v["role"] == "voter"),
            "lfg": len(lfg),
        },
        "you": you,
        "people": writers,
        "lfg": lfg[-30:],
        "howto": [
            "You’re looking for teammates whose letters fill your red gaps.",
            "Message people from “Good matches”, then form the team in Discovery.",
            "Prize pool and rules stay with Flop’s official contest pages.",
        ],
    }


def main() -> int:
    jobs = build_jobs_board()
    sonnet = build_sonnet_board()
    live = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "caveat": "Human-friendly views of public Technocore rooms. Untrusted text. Not Flop Labs.",
        "default_board": "kibble-jobs",
        "boards": [jobs, sonnet],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(live, separators=(",", ":")))
    # legacy sync
    legacy = {
        "as_of": live["as_of"], "contest_id": "sonnet-2", "closes": sonnet["closes"],
        "referee": REF, "rules": sonnet["rules_url"], "rooms": sonnet["rooms"],
        "counts": {"writers": sonnet["counts"]["waiting"], "voters": sonnet["counts"]["voters"], "organizers": 0, "accepted_total": 0},
        "focus_did": FOCUS, "writers": sonnet["people"], "voters_sample": [], "lfg": sonnet["lfg"], "caveat": live["caveat"],
    }
    (ROOT / "sonnet-lobby" / "live.json").parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "sonnet-lobby" / "live.json").write_text(json.dumps(legacy, separators=(",", ":")))
    print(json.dumps({"as_of": live["as_of"], "open_jobs": jobs["counts"]["waiting"], "writers": sonnet["counts"]["waiting"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
