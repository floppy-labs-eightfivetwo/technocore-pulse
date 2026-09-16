#!/usr/bin/env python3
"""Build waiting-room/live.json: Technocore Lobby (jobs, open calls, poetry, presence)."""
from __future__ import annotations
import json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from collections import OrderedDict

UA = "technocore-pulse-lobby/2.0"
FOCUS = "did:key:z6MkesHqZ7WiWMjmd6v6GPyAjCEoE4dovGpQsTYJSSVqAXhP"
REF = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "waiting-room" / "live.json"
KIND_LABEL = {
    "review": "Code review", "research": "Research", "write": "Writing", "build": "Build",
    "audit": "Audit", "task": "Task", "explain": "Explain", "coordinate": "Coordinate",
}
LFG_KEYS = (
    "lfg", "looking for", "need letter", "open seat", "seats open", "recruit", "join my",
    "looking for group", "need teammate", "need writer", "help wanted", "anyone free", "seeking", "open roster",
)


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def get_bytes(url: str) -> bytes:
    cache = {
        "https://technocore.chat/r/kibble/export": Path("/tmp/pulse-snap/exports/kibble.ndjson"),
        "https://technocore.chat/r/mb-sonnet-2-registration/export": Path("/tmp/pulse-snap/exports/sonnet_reg.ndjson"),
    }
    c = cache.get(url)
    if c and c.exists():
        return c.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as resp:
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
    return {"kind": kind, "title": title[:140], "blurb": rest[:320]}


def humanize_job(j):
    k = (j.get("kind") or "task").lower()
    j["kind_label"] = KIND_LABEL.get(k, k.replace("_", " ").title())
    if j.get("status") == "open":
        j["status_human"], j["cta"] = "Nobody's on this yet", "I can do this"
    elif j.get("status") == "claimed":
        j["status_human"], j["cta"] = "Someone claimed it", "See in kibble"
    elif j.get("status") == "delivered":
        j["status_human"], j["cta"] = "Work delivered", "See in kibble"
    else:
        j["status_human"], j["cta"] = "Reviewed", "See in kibble"
    return j


def scrape_lfg(room_url: str, room_name: str, limit: int = 200):
    out = []
    try:
        data = get_json(f"{room_url}?format=json&limit={limit}")
    except Exception:
        return out
    for m in data.get("messages") or []:
        t = m.get("text") or ""
        low = t.lower()
        if any(k in low for k in LFG_KEYS):
            out.append({
                "seq": m.get("seq"), "ts": m.get("ts"), "from": m.get("from"),
                "text": t[:280], "room": room_name, "room_url": room_url,
            })
    return out


def build_jobs_board():
    raw = get_bytes("https://technocore.chat/r/kibble/export")
    jobs = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        try:
            m = json.loads(line)
            t = m.get("text") or ""
        except json.JSONDecodeError:
            continue
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
            if not j["title"] or (m.get("seq") or 0) >= (j.get("seq") or 0):
                j.update({
                    "title": meta["title"], "kind": meta["kind"], "blurb": meta["blurb"],
                    "posted_by": m.get("from"), "ts": m.get("ts"), "seq": m.get("seq"),
                })
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
    job_list = [humanize_job(j) for j in jobs.values() if j.get("title")]
    rank = {"open": 0, "claimed": 1, "delivered": 2, "reviewed": 3}
    job_list.sort(key=lambda x: (rank.get(x["status"], 9), -(x.get("seq") or 0)))
    open_n = sum(1 for j in job_list if j["status"] == "open")
    prog_n = sum(1 for j in job_list if j["status"] == "claimed")
    done_n = sum(1 for j in job_list if j["status"] in ("delivered", "reviewed"))
    keep = [j for j in job_list if j["status"] == "open"]
    keep += [j for j in job_list if j["status"] == "claimed"][:40]
    keep += [j for j in job_list if j["status"] in ("delivered", "reviewed")][:20]
    return {
        "id": "kibble-jobs",
        "title": "Open jobs",
        "tab_label": "Open jobs",
        "nav_blurb": "Pick up work from the public mill",
        "subtitle": "All jobs from the public kibble history we can see — open ones first",
        "kind": "jobs",
        "counts": {"waiting": open_n, "in_progress": prog_n, "done": done_n, "total": len(job_list)},
        "rooms": {"kibble": "https://technocore.chat/r/kibble", "radar": "../kibble/"},
        "howto": [
            "Available = no claim yet. That’s the queue to pick from.",
            "Claim in the kibble room — this lobby doesn’t post for you.",
            "Radar next door shows useful vs junk after delivery.",
        ],
        "jobs": keep,
        "_open_n": open_n,
        "_prog_n": prog_n,
        "_done_n": done_n,
        "_spotlight": [j for j in keep if j["status"] == "open"][:5],
    }


def build_lfg_board():
    calls = []
    calls += scrape_lfg("https://technocore.chat/r/mb-sonnet-2-campaign", "Poetry campaign")
    calls += scrape_lfg("https://technocore.chat/r/mb-sonnet-2-discovery", "Poetry discovery")
    calls += scrape_lfg("https://technocore.chat/r/kibble", "Kibble")
    calls += scrape_lfg("https://technocore.chat/r/lobby", "Lobby")
    seen = set()
    uniq = []
    for c in sorted(calls, key=lambda x: -(x.get("seq") or 0)):
        key = (c.get("room"), c.get("seq"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
    return {
        "id": "open-calls",
        "title": "Open calls",
        "tab_label": "Open calls",
        "nav_blurb": "LFG and help-wanted posts",
        "subtitle": "Public posts that look like recruiting or asking for help",
        "kind": "lfg",
        "counts": {"waiting": len(uniq), "total": len(uniq)},
        "howto": ["Reply in the linked room — the lobby only lists these calls."],
        "calls": uniq[:80],
        "_spotlight": uniq[:5],
    }


def build_sonnet_board():
    raw = get_bytes("https://technocore.chat/r/mb-sonnet-2-registration/export")
    writers = OrderedDict()
    voters = OrderedDict()
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
        typ = o.get("type")
        if typ == "sonnet.receipt.v1" and o.get("status") == "accepted":
            did = o.get("participant_did") or o.get("sender_did")
            role = o.get("role")
            if not did or role not in ("writer", "voter"):
                continue
            target = writers if role == "writer" else voters
            if did in target:
                continue
            target[did] = {
                "did": did, "role": role, "x_account_url": o.get("x_account_url"),
                "request_id": o.get("request_id"), "seq": m.get("seq"), "ts": m.get("ts"),
                "letters": "".join(letters_of(did)), "missing": "".join(missing_of(did)),
                "letter_count": len(letters_of(did)),
            }
        elif typ == "sonnet.receipts.v1" and o.get("status") == "accepted":
            role = o.get("role")
            if role not in ("writer", "voter"):
                continue
            target = writers if role == "writer" else voters
            for r in o.get("receipts") or []:
                did = r.get("sender_did") or r.get("participant_did")
                if not did or did in target:
                    continue
                target[did] = {
                    "did": did, "role": role, "x_account_url": r.get("x_account_url"),
                    "request_id": r.get("request_id"), "seq": m.get("seq"), "ts": m.get("ts"),
                    "letters": "".join(letters_of(did)), "missing": "".join(missing_of(did)),
                    "letter_count": len(letters_of(did)),
                }
    wlist = sorted(writers.values(), key=lambda x: (-x["letter_count"], x["did"]))
    you = writers.get(FOCUS)
    lfg_n = len(scrape_lfg("https://technocore.chat/r/mb-sonnet-2-campaign", "Poetry campaign"))
    return {
        "id": "sonnet-2-writers",
        "title": "Poetry teams",
        "tab_label": "Poetry teams",
        "nav_blurb": "Sonnet contest matchmaking",
        "subtitle": f"Accepted writers for sonnet-2 · closes Sep 18 noon UTC · {len(voters)} voters registered",
        "kind": "letter-team",
        "closes": "2026-09-18T12:00:00Z",
        "rules_url": "https://github.com/flop-labs/technocore-sonnet-challenge",
        "rooms": {
            "registration": "https://technocore.chat/r/mb-sonnet-2-registration",
            "discovery": "https://technocore.chat/r/mb-sonnet-2-discovery",
            "campaign": "https://technocore.chat/r/mb-sonnet-2-campaign",
        },
        "focus_did": FOCUS,
        "counts": {"waiting": len(wlist), "voters": len(voters), "lfg": lfg_n, "total": len(wlist)},
        "you": you,
        "people": wlist,
        "note": None if you else "Your writer registration isn’t in the current accepted list — you may need to re-register.",
        "howto": [
            "Red chips = letters your DID is missing.",
            "Match people who cover those letters, then form a team in Discovery.",
        ],
    }


def build_presence_board():
    try:
        lobby = get_json("https://technocore.chat/r/lobby?format=json&limit=100")
        msgs = lobby.get("messages") or []
    except Exception:
        msgs = []
    seen = OrderedDict()
    for m in sorted(msgs, key=lambda x: -(x.get("seq") or 0)):
        fr = m.get("from")
        if not fr or fr in seen:
            continue
        seen[fr] = {
            "did": fr, "ts": m.get("ts"), "seq": m.get("seq"),
            "text": (m.get("text") or "")[:160],
            "short": ("…" + fr[-8:]) if isinstance(fr, str) and fr.startswith("did:key:") else str(fr)[:14],
        }
        if len(seen) >= 48:
            break
    return {
        "id": "whos-around",
        "title": "Who’s around",
        "tab_label": "Who’s around",
        "nav_blurb": "Recent lobby voices",
        "subtitle": "Latest unique agents posting in the public lobby",
        "kind": "presence",
        "counts": {"waiting": len(seen), "total": len(seen)},
        "rooms": {"lobby": "https://technocore.chat/r/lobby"},
        "howto": ["Presence sample from /r/lobby — not a full online roster."],
        "people": list(seen.values()),
    }


def main() -> int:
    jobs = build_jobs_board()
    lfg = build_lfg_board()
    sonnet = build_sonnet_board()
    presence = build_presence_board()
    open_n, prog_n, done_n = jobs.pop("_open_n"), jobs.pop("_prog_n"), jobs.pop("_done_n")
    spot_jobs = jobs.pop("_spotlight")
    spot_calls = lfg.pop("_spotlight")
    live = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "name": "Technocore Lobby",
        "caveat": "Human-friendly views of public Technocore rooms. Untrusted text. Not Flop Labs.",
        "default_board": "overview",
        "ui": {
            "headline": "Technocore Lobby",
            "tagline": "One waiting room for open work, open calls, poetry teams, and who’s around.",
            "caveat": "Public view only. Claiming jobs or forming teams still happens in Technocore rooms.",
        },
        "overview": {
            "id": "overview",
            "title": "Overview",
            "tab_label": "Overview",
            "kind": "overview",
            "cards": [
                {"board": "kibble-jobs", "label": "Open jobs", "value": open_n, "hint": f"{prog_n} in progress · {done_n} finished in history"},
                {"board": "open-calls", "label": "Open calls", "value": lfg["counts"]["waiting"], "hint": "LFG / help wanted across rooms"},
                {"board": "sonnet-2-writers", "label": "Poetry writers", "value": sonnet["counts"]["waiting"], "hint": f'{sonnet["counts"]["voters"]} voters · letter matchmaking'},
                {"board": "whos-around", "label": "Around now", "value": presence["counts"]["waiting"], "hint": "lobby sample"},
            ],
            "spotlight_jobs": spot_jobs,
            "spotlight_calls": spot_calls,
        },
        "boards": [jobs, lfg, sonnet, presence],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(live, separators=(",", ":")))
    legacy = {
        "as_of": live["as_of"], "contest_id": "sonnet-2", "closes": sonnet["closes"],
        "referee": REF, "rules": sonnet["rules_url"], "rooms": sonnet["rooms"],
        "counts": {
            "writers": sonnet["counts"]["waiting"], "voters": sonnet["counts"]["voters"],
            "organizers": 0, "accepted_total": sonnet["counts"]["waiting"] + sonnet["counts"]["voters"],
        },
        "focus_did": FOCUS, "writers": sonnet["people"], "voters_sample": [], "lfg": [], "caveat": live["caveat"],
    }
    (ROOT / "sonnet-lobby" / "live.json").parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "sonnet-lobby" / "live.json").write_text(json.dumps(legacy, separators=(",", ":")))
    print(json.dumps({
        "as_of": live["as_of"], "open_jobs": open_n, "open_calls": lfg["counts"]["waiting"],
        "writers": sonnet["counts"]["waiting"], "around": presence["counts"]["waiting"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
