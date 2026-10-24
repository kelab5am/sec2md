"""Explain each document whose output the HTML-comments change altered.

The run and diff steps are the positioned-layout corpus check's `compare.py`. This step reads
its `results.json` and both sides' Markdown dumps and, for every changed document, compares
the whitespace-separated tokens of the two dumps:

- **explained:** no token is added, the pages keep their numbers and display pages, and every
  removed token occurs in the source document's comments (Comment, Declaration, Doctype or
  ProcessingInstruction strings, as lxml parses them);
- **review:** anything else, listed with its added and unexplained tokens and its pages.

Each document is also labelled with the comment sources its removed tokens come from.

    python explain.py --docs <docs.json> --results <results.json> --main-dumps <dir>
                      --branch-dumps <dir> --out <explained.json>
"""
import argparse
import gzip
import json
import re
import warnings
from collections import Counter

from bs4 import BeautifulSoup
from bs4.element import Comment, Declaration, Doctype, ProcessingInstruction

_MARKER = re.compile(r"^<<<page (\d+) display=(.*)>>>$", re.M)
# Which comment a removed token came from, by a token only that source writes.
_CAUSES = (
    ("toppan-field", "Field:"),
    ("edgar-index", "BANNER"),
    ("workiva", "Wdesk"),
    ("doctype", '"-//W3C//DTD'),
    ("broadridge", "Broadridge"),
)


def _read(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    return gzip.decompress(raw) if path.endswith(".gz") else raw


def _comment_tokens(path):
    from sec2md.encoding import decode_html

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        soup = BeautifulSoup(decode_html(_read(path))[0], "lxml")
    kinds = (Comment, Declaration, Doctype, ProcessingInstruction)
    tokens = Counter()
    for string in soup.find_all(string=lambda s: isinstance(s, kinds)):
        tokens.update(str(string).split())
    return tokens


def _dump(directory, name):
    with open(f"{directory}/{name}", encoding="utf-8") as handle:
        text = handle.read()
    return _MARKER.findall(text), Counter(_MARKER.sub("", text).split())


def explain(args):
    with open(args.docs, encoding="utf-8") as handle:
        paths = {doc["id"]: doc["path"] for doc in json.load(handle)["documents"]}
    with open(args.results, encoding="utf-8") as handle:
        changed = [d for d in json.load(handle)["differing"] if d["changed"]]
    rows = []
    for doc in changed:
        main_pages, main_tokens = _dump(args.main_dumps, doc["dumps"][0])
        branch_pages, branch_tokens = _dump(args.branch_dumps, doc["dumps"][1])
        added = branch_tokens - main_tokens
        removed = main_tokens - branch_tokens
        unexplained = removed - _comment_tokens(paths[doc["id"]])
        causes = [cause for cause, token in _CAUSES if removed[token]] or ["other"]
        verdict = "explained" if not added and not unexplained and main_pages == branch_pages else "review"
        rows.append({
            "id": doc["id"],
            "changed": doc["changed"],
            "verdict": verdict,
            "causes": causes,
            "removed": sum(removed.values()),
        })
        if verdict == "review":
            rows[-1].update(added=dict(added), unexplained=dict(unexplained),
                            pages=[main_pages, branch_pages])
    summary = Counter(row["verdict"] for row in rows)
    causes = Counter("+".join(row["causes"]) for row in rows)
    groups = Counter(row["id"].split(":", 1)[0] for row in rows)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump({"changed": len(rows), "verdicts": dict(summary), "causes": dict(causes),
                   "groups": dict(groups), "documents": rows}, handle, indent=1)
    print(f"{len(rows)} changed: {dict(summary)}; causes {dict(causes)}; groups {dict(groups)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for flag in ("--docs", "--results", "--main-dumps", "--branch-dumps", "--out"):
        parser.add_argument(flag, required=True)
    explain(parser.parse_args())
