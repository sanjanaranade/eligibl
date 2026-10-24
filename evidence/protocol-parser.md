# Protocol Parser evidence

Date: 2026-10-24  
Study: Saffron Extract Supplementation and Sleep Quality in Middle-Aged Adults (`NCT07497698`)  
Source: `eligibl/data/protocol_source.txt`

## Live run

The parser called `gpt-6-luna` through Portkey and produced the committed `data/protocol.json`. The structured response was checked against the JSON schema and then checked in code against source title, NCT number, count, order, type, and exact original wording. The successful validated checklist contains 5 inclusion and 7 exclusion criteria. Clinic-check criteria are not treated as chat-screenable.

The usage log records the actual attempts, including responses rejected by local validation before the final accepted output. The accepted call used 500 input tokens, 2,058 output tokens, 0 cached input tokens, and estimated $0.0013098 per call. Two preceding responses were also logged while tuning the response-size cap and validating negative phrasing; they were not saved as the protocol. See `logs/usage.jsonl` for per-call details.

## Offline verification

The test suite covers required-field/source correspondence, exclusion negation, missing criteria rejection, and source-hash caching. The cache is valid only while `data/protocol.sha256` matches the source file's SHA-256 digest.
