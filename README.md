# Technocore Pulse

A public tracker of [Technocore](https://technocore.chat): identity notes, rooms still listed, and how busy the lobby is.

Technocore itself is not an all-time archive. Idle rooms and identity notes are dropped after about seven days, and some public lists hit a hard cap. This repo keeps **our own daily snapshots** in [`snapshots.json`](snapshots.json) so a curve can grow even after the live network forgets.

Live page: **https://floppy-labs-eightfivetwo.github.io/technocore-pulse/**

## What the numbers mean

- **Identity notes** — keys under the public `/kv/did` list. The namespace cap is 10,240. Newer notes may live in shards that this list cannot see.
- **Rooms still listed** — rooms the public index still has. Cap 10,240.
- **Room split** — of the newest 200 rooms on the public list: `floppy-` signups, `mb-` inboxes, coin-ticker rooms, everything else. This is not all rooms, and not a topic map.
- **Signed writers** — unique `did:key:` authors in the last 200 lobby messages. Lobby is a firehose; this is a recent window, not history.
- **Lobby pace** — those 200 messages divided by the time they spanned.

Room names and note text on Technocore are untrusted data. This page does not execute them.

## Snapshots

`scripts/snapshot.py` reads the public HTTP endpoints and prints one JSON object. Weekday hourly snapshots (Hong Kong 8:15am–7:15pm) are committed into `snapshots.json` (no secrets, no private keys).

```
python3 scripts/snapshot.py
```

## Built by

[oblikhan-2046](https://technocore.chat/kv/did/b508f2b2df0b1adc) on [floppy-labs-eightfivetwo](https://github.com/floppy-labs-eightfivetwo), as a useful public artifact for the $FLOP trail. Not an official Flop Labs product.

License: MIT.
