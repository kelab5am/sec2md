"""Probe: judge's per-frame early stop against a search that stops once the start has both verdicts."""
from sec2md.table_alignment import Expectation, judge, MAX_STATES, SEPARATOR, header_atoms

def global_stop_states(header, expectation, max_states=10**9):
    """The same search, but every verdict found is propagated to all open frames at once."""
    atoms = [atom.casefold() for atom in header_atoms(header)]
    relevant = sorted(set(expectation.required) | set(expectation.conflicts))
    index = {key: i for i, key in enumerate(relevant)}
    need = [expectation.need.get(key, 0) for key in relevant]
    required = [index[k] for k in expectation.required]
    conflicts = [index[k] for k in expectation.conflicts]
    size = len(atoms)
    memo, created = {}, 1
    start = (0, (0,) * len(relevant))
    stack = [[start, 0, 0]]
    seen_start = 0
    def consistent(counts):
        return all(counts[r] >= need[r] for r in required) and all(counts[c] <= need[c] for c in conflicts)
    while stack:
        frame = stack[-1]
        (position, counts), end, reachable = frame
        if seen_start == 3:
            return "ambiguous", created
        if reachable == 3 or end >= size:
            memo[frame[0]] = reachable
            stack.pop()
            if stack:
                stack[-1][2] |= reachable
            continue
        frame[1] = end + 1
        key = SEPARATOR.join(atoms[position:end + 1])
        label = index.get(key, -1)
        if label >= 0 and counts[label] <= need[label]:
            counts = counts[:label] + (counts[label] + 1,) + counts[label + 1:]
        child = (end + 1, counts)
        if child in memo:
            frame[2] |= memo[child]
            seen_start |= memo[child]
            continue
        created += 1
        if created > max_states:
            return "budget", created - 1
        if end + 1 == size:
            verdict = 1 if consistent(counts) else 2
            memo[child] = verdict
            frame[2] |= verdict
            seen_start |= verdict   # global: every verdict found is reachable from the start
        else:
            stack.append([child, end + 1, 0])
    return {1: "aligned", 2: "misaligned", 3: "ambiguous"}[memo[start]], created

for k in (15, 19):
    conflicts = [f"c{i}" for i in range(1, k + 1)]
    need = {"a — b": 1, **{c: 1 for c in conflicts}}
    expectation = Expectation(1, (), ("a — b",), need, {c: c.upper() for c in conflicts})
    header = SEPARATOR.join(["A", "B", *[c.upper() for c in conflicts]])
    print(k, "judge:", judge(header, expectation, max_states=10**7), "| global stop:", global_stop_states(header, expectation),
          "| judge at the 100,000 bound:", judge(header, expectation).outcome)
