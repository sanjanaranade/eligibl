# Agent 4 Outreach evidence

Captured 2026-10-24. The recipient and all candidate records used in tests are synthetic.

## Automated checks

Command: `python -m pytest -q`

Result: **74 passed**.

Outreach tests use a mocked `call_agent` and verify the approved-candidate tool surface returns exactly four summary fields (first name, study title, status, chosen slot), refuses requests for another candidate, and never includes candidate transcript text in the model prompt. The approved path stages three drafts from `config/availability.json`; the not-a-match path stages one short draft that mentions ResearchMatch without a personal screening reason. Reminder times are computed in code relative to the coordinator-selected sample slot.

Validation tests exercise empty fields, exact study-team contact line, placeholder rejection, voluntary participation language, 150-word cap, inclusion of all three invitation slots, chosen-slot reminders, unauthorized benefit/payment promises, ResearchMatch/other-studies wording, and personal health-detail wording. Invalid drafts are blocked before they can be queued. If the API key is missing, the coordinator action is not saved and the route names the expected key and `.env` locations.

## Queue safety

The email page allows draft edits and a coordinator action labeled **Approve to send**. Server-side validation runs after the edit is saved. Approval sets status to `queued`, adds a timestamped `email_queued_demo` coordinator action, and marks the candidate contacted. It does not send anything: `sent_at` remains null and the API response includes `actually_sent: false`. The page displays “Queued (demo, not actually sent)” with the scheduled time.

Tests verify a draft missing the study-team contact line is rejected with a friendly message and remains a draft; after valid edits, it queues successfully and still has no sent timestamp. No live Portkey request or email transmission was performed for these tests.

Flask was started with debug and auto-reload disabled; `/coordinator`, `/coordinator/email-drafts`, and `/health` all returned HTTP 200. The process was stopped after this local smoke check.

## Sample slot configuration

Three synthetic November 2026 visit options and a reserved example contact address are configured in `config/availability.json`. The invitation includes all three options. The selected planning slot anchors the two-day-prior and 8:00 AM local-time reminders. Replace both slots and contact information before any real-world use.
