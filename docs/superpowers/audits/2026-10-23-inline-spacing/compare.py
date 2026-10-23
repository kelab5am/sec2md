"""Compare base and new corpus Markdown: classify every whitespace change.

usage: python compare.py <base_dir> <new_dir> <report.json>
"""
import difflib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def cls(c):
    if c == "":
        return "^"
    if c.isdigit():
        return "9"
    if c.isalpha():
        return "a"
    return c


def space_edits(old, new):
    """Removed and added spaces when old and new differ only in spaces, else None."""
    if old.replace(" ", "") != new.replace(" ", ""):
        return None
    i = j = 0
    removed, added = [], []
    while i < len(old) or j < len(new):
        if i < len(old) and j < len(new) and old[i] == new[j]:
            i += 1; j += 1
        elif i < len(old) and old[i] == " ":
            removed.append(i); i += 1
        else:
            added.append(j); j += 1
    return removed, added


def main(base_dir, new_dir, report):
    base_dir, new_dir = Path(base_dir), Path(new_dir)
    cats = Counter()
    examples = defaultdict(list)
    added_examples = []
    other = []
    per_file = {}
    for bf in sorted(base_dir.glob("*.md")):
        nf = new_dir / bf.name
        old_lines = bf.read_text(encoding="utf-8").split("\n")
        new_lines = nf.read_text(encoding="utf-8").split("\n")
        sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
        removed_n = added_n = other_n = 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            olds, news = old_lines[i1:i2], new_lines[j1:j2]
            if tag == "replace" and len(olds) == len(news):
                pairs = list(zip(olds, news))
            else:
                pairs = [("\n".join(olds), "\n".join(news))]
            for o, n in pairs:
                edits = space_edits(o, n)
                if edits is None:
                    other_n += 1
                    other.append({"file": bf.name, "old": o[:600], "new": n[:600]})
                    continue
                removed, added = edits
                removed_n += len(removed); added_n += len(added)
                for i in removed:
                    key = cls(o[i - 1] if i else "") + "|" + cls(o[i + 1] if i + 1 < len(o) else "")
                    cats[key] += 1
                    if len(examples[key]) < 25:
                        examples[key].append(f"{bf.name}: ...{o[max(0, i - 30):i + 30]}...")
                for j in added:
                    if len(added_examples) < 100:
                        added_examples.append(f"{bf.name}: ...{n[max(0, j - 30):j + 30]}...")
        per_file[bf.name] = {"removed_spaces": removed_n, "added_spaces": added_n, "other_changes": other_n,
                             "identical": old_lines == new_lines}
    Path(report).write_text(json.dumps({
        "per_file": per_file, "categories": cats.most_common(),
        "examples": examples, "added_examples": added_examples, "other": other[:400],
        "other_total": len(other),
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print("files", len(per_file), "identical", sum(v["identical"] for v in per_file.values()))
    print("removed", sum(v["removed_spaces"] for v in per_file.values()),
          "added", sum(v["added_spaces"] for v in per_file.values()), "other", len(other))
    for k, v in cats.most_common(40):
        print(f"{k!r}: {v}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
