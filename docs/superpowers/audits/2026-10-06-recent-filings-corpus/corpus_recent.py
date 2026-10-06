"""The recent filings corpus: every document in manifest.json, checked against its SHA-256.

    import corpus_recent
    docs, skipped = corpus_recent.documents(cache)   # cache: outputs/recent-filings-corpus

`documents(cache)` has the shape of Phase A's `corpus_phase_a.documents()`: a list of
(id, group, raw bytes) and a list of skipped entries. The documents are the manifest's
(written by `fetch_recent.py download`), read from the cache in sorted file-name order. The
ids are `recent:<file name>` and the group is `recent`. A file that is missing, or whose
SHA-256 differs from the manifest's, raises: it is an error, never a skip. A `.htm` file in
the cache that the manifest does not list is not loaded; it is reported in `skipped`.
"""
import glob
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "manifest.json")
GROUP = "recent"


def documents(cache, manifest=MANIFEST):
    """([(id, "recent", raw bytes)] in sorted file order, skipped) for the manifest's documents."""
    with open(manifest, encoding="utf-8") as handle:
        entries = json.load(handle)["documents"]
    found = []
    for entry in sorted(entries, key=lambda e: e["file"]):
        path = os.path.join(cache, entry["file"])
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{entry['file']} is in {manifest} but not in {cache}")
        with open(path, "rb") as handle:
            raw = handle.read()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != entry["sha256"]:
            raise ValueError(f"{entry['file']}: SHA-256 {digest} ({len(raw):,} bytes) is not the"
                             f" manifest's {entry['sha256']} ({entry['bytes']:,} bytes)")
        found.append((f"recent:{entry['file']}", GROUP, raw))
    listed = {entry["file"] for entry in entries}
    in_cache = sorted(os.path.basename(p) for p in glob.glob(os.path.join(cache, "*.htm")))
    skipped = [f"recent:{name} (not in manifest.json)" for name in in_cache if name not in listed]
    return found, skipped
