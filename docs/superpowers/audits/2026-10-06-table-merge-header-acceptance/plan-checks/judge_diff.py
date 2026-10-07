"""Random headers and expectations: round-4 judge (28298ff) against round-5 judge (8f4991e).

Each side runs in its own process (different PYTHONPATH); this file writes or compares JSON.
"""
import json, random, sys
from sec2md.table_alignment import Expectation, PathEntry, SEPARATOR, judge

def cases(n, seed=20261006):
    rng = random.Random(seed)
    words = ["a", "b", "c", "d", "e", "a — b", "c — d", "2025", "2024", "rmb"]
    out = []
    for _ in range(n):
        keys = rng.sample(words, rng.randint(1, 6))
        required = tuple(dict.fromkeys(rng.sample(keys, rng.randint(1, len(keys)))))
        conflicts = {k: k.upper() for k in keys if k not in required and rng.random() < 0.8}
        need = {k: rng.randint(1, 2) for k in keys}
        path = tuple(PathEntry(k, k, (), ()) for k in rng.sample(keys, rng.randint(0, len(keys))))
        atoms = [rng.choice(words + ["x", "y"]) for _ in range(rng.randint(1, 12))]
        header = SEPARATOR.join(atoms)
        out.append((header, Expectation(1, path, required, need, conflicts)))
    return out

if __name__ == "__main__":
    if sys.argv[1] == "run":
        result = []
        for header, expectation in cases(int(sys.argv[2])):
            v = judge(header, expectation, max_states=int(sys.argv[3]))
            result.append([v.outcome, v.states, list(v.conflicting)])
        json.dump(result, open(sys.argv[4], "w"))
    else:
        old, new = json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
        outcome = sum(a[0] != b[0] for a, b in zip(old, new))
        conflicting = sum(a[2] != b[2] for a, b in zip(old, new))
        more = sum(b[1] > a[1] for a, b in zip(old, new))
        changed_budget = sum(a[0] == "budget" and b[0] != "budget" for a, b in zip(old, new))
        print(f"cases {len(old)}; outcome differs {outcome}; conflicting differs {conflicting}; "
              f"new uses more states {more}; old budget -> new not {changed_budget}; "
              f"outcomes old {sorted(set(a[0] for a in old))}")
