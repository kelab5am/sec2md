# Audited SEC HTML corpus

These seven files are the offline, byte-frozen SEC HTML sources audited by the
2026-08-28 UTC SEC HTML bakeoff. The two source manifests used as capture
evidence were `source-manifest.json` and `supplemental-source-manifest.json`.
The uncompressed SHA-256 values below are repeated in `manifest.json` and are
verified before any fixture is returned by the loader.

| Fixture | SEC archive URL | Uncompressed SHA-256 |
| --- | --- | --- |
| aapl-2023-10k | https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm | bda1f34435199672c16ecdf2034c650872d2cac8399ed0d179fc25450b080b90 |
| nvda-2026-10k | https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm | 73d81f5a111abcf72426c840871e76f5f5edc9631f436d495a86b6f87306d58b |
| nvda-2002-10k | https://www.sec.gov/Archives/edgar/data/1045810/000101287002002262/d10k.htm | 04136c61bb8ea9490da4916f358a2275f019ed6536878715da412d7056a0739d |
| nvda-2026-q2-10q | https://www.sec.gov/Archives/edgar/data/1045810/000104581026000075/nvda-20260726.htm | e2634e509c241c5f45e3f6c115dc38a85645e5fdbee760b4a04f5e9035f6f7a9 |
| nvda-2026-08-26-8k | https://www.sec.gov/Archives/edgar/data/1045810/000104581026000073/nvda-20260826.htm | 84335b3247873da9fc91b4d9aa146be012801158183a7e9b0e98f0d31e50d0ea |
| nvda-2026-ex99-1 | https://www.sec.gov/Archives/edgar/data/1045810/000104581026000073/q2fy27pr.htm | 1809cb206590dcfeb959f3a1a64157f4e5ee42788ec51289b74f3ea299931eb7 |
| nvda-2026-ex99-2 | https://www.sec.gov/Archives/edgar/data/1045810/000104581026000073/q2fy27cfocommentary.htm | 6a522635d049044b2ff9ff63cb78220cf29d960e96614c88afe30560c3ee0659 |

The `.html.gz` members use deterministic gzip (`mtime=0`, empty embedded
filename). They are immutable test inputs: update a fixture only with a new
audited source, hash, and reviewable manifest change. Tests never access the
network or write to this directory.

The accuracy suite is run with:

```powershell
.\.venv\Scripts\python -m pytest tests/accuracy -v
```
