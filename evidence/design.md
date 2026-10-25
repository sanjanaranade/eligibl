# Eligibl design pass

Implemented the warm cream, teal, and apricot patient-portal visual system across the welcome, candidate screening, coordinator dashboard/review drawer, protocol, safety, and outreach pages. Added the inline-SVG wordmark and favicon, Fraunces/Inter with local fallbacks, responsive layouts, accessible focus states, reduced-motion behavior, status icons, criterion evidence highlighting, a candidate journey timeline, loading-check animation, and coordinator-only approval toast.

Refined the dashboard and participant experience against the supplied visual references. Added persistent cross-navigation between coordinator pages and `/screen`, plus a reciprocal coordinator link in the candidate header. Kept the question count and estimated-time cue together during live chat updates, and gave the completion state a calmer, centered presentation.

Fixed a live-state bug discovered during the smoke test: the safety suite mirrors a `$0.001` test-budget event into the dashboard audit database, and the old pause check treated any such event as a real `$2.00` daily-budget stop. The pause check now matches the event's recorded cap to the currently configured cap. The synthetic safety event remains visible in the Safety log but no longer blocks live screening. The 24 evaluation personas remain in the evaluation corpus, not preloaded as participant screenings. At initial diagnosis the operational database had zero sessions; a live preview later created one in-progress synthetic session. The dashboard's “Screened” metric counts completed sessions, so remains zero until that chat finishes.

## Verification

- `.venv/bin/python -m pytest -q`: **113 passed**.
- Started the Flask app briefly on `127.0.0.1:5051` with debug and reloader disabled (port 5050 was left untouched).
- HTTP smoke checks returned **200** for `/`, `/coordinator`, `/screen`, `/coordinator/protocol`, `/coordinator/safety`, and `/coordinator/email-drafts`.
- Real model-backed start smoke test with the synthetic name `Demo`, in a temporary database: **HTTP 200**, first question “Are you between 18 and 65 years old?”, 2 model calls, **$0.000339** recorded; temporary candidate and logs were discarded.
- After clearing the false pause, the live preview accepted a synthetic screening start and a participant reply (HTTP 200); the session is persisted as in progress.
- The smoke-test server was stopped after verification, then the updated app was restarted at `http://127.0.0.1:5051` for the user preview.

Fraunces and Inter are loaded from Google Fonts when online and fall back to Georgia and system sans-serif when offline. No external images or JavaScript packages were added for the design.
