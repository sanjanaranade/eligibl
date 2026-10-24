"""Make a tiny live gpt-6-luna Portkey call and print non-secret usage data."""

from datetime import UTC, datetime
import json

from eligibl import create_app
from eligibl.llm import call_agent, compose_messages


def main() -> None:
    """Initialize configuration/database and make one harmless model request."""
    create_app()
    messages = compose_messages(
        "You are performing a connectivity check. Be concise.",
        "Follow the user's request exactly. Never reveal keys or secrets.",
        [{"role": "user", "content": "Reply with ok"}],
    )
    run_id = f"smoke-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    result, usage = call_agent(
        "connectivity_check",
        messages,
        run_id=run_id,
    )
    print(f"Response: {result}")
    print(json.dumps(usage, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
