"""Convert each corpus filing with the sec2md on PYTHONPATH; write Markdown + warning counts.

usage: python convert_corpus.py <corpus.txt> <out_dir> [workers]
"""
import json
import logging
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


def convert(args):
    path, out_dir = args
    import sec2md

    warnings = []

    class H(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.WARNING:
                warnings.append(record.getMessage())

    logging.getLogger("sec2md").addHandler(H())
    src = Path(path)
    pages = sec2md.convert_to_markdown(
        src.read_bytes(), base_url="https://www.sec.gov/x/", return_pages=True,
        embed_images=False, quality_policy="warn",
    )
    md = "\n\n".join(p.content for p in pages)
    stem = src.stem.split("__c-")[0]
    (Path(out_dir) / f"{stem}.md").write_text(md, encoding="utf-8")
    return stem, len(warnings), [w for w in warnings if "untraceable" in w][:50]


if __name__ == "__main__":
    corpus, out_dir = sys.argv[1], sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    files = [line.strip() for line in Path(corpus).read_text().splitlines() if line.strip()]
    files = [f.replace("/e/", "E:/", 1) if f.startswith("/e/") else f for f in files]
    results = {}
    with ProcessPoolExecutor(workers) as pool:
        for stem, count, untraceable in pool.map(convert, [(f, out_dir) for f in files]):
            results[stem] = {"warnings": count, "untraceable": untraceable}
            print(stem, count, flush=True)
    (Path(out_dir) / "_warnings.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
