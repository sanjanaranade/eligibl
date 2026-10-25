# Eligibl design pass

Implemented the warm cream, teal, and apricot patient-portal visual system across the welcome, candidate screening, coordinator dashboard/review drawer, protocol, safety, and outreach pages. Added the inline-SVG wordmark and favicon, Fraunces/Inter with local fallbacks, responsive layouts, accessible focus states, reduced-motion behavior, status icons, criterion evidence highlighting, a candidate journey timeline, loading-check animation, and coordinator-only approval toast.

## Verification

- `.venv/bin/python -m pytest -q`: **111 passed**.
- Started the Flask app briefly on `127.0.0.1:5051` with debug and reloader disabled (port 5050 was left untouched).
- HTTP smoke checks returned **200** for `/`, `/coordinator`, `/screen`, `/coordinator/protocol`, `/coordinator/safety`, and `/coordinator/email-drafts`.
- Stopped the temporary server after checks.

Fraunces and Inter are loaded from Google Fonts when online and fall back to Georgia and system sans-serif when offline. No external images or JavaScript packages were added for the design.
