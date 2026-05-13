from app.schemas.agent import ClarificationItem


def assemble(description: str, clarifications: list[ClarificationItem]) -> str:
    """Combine the original description and all Q&A pairs into a single prompt string.

    Round count is derived from len(clarifications) — no server-side state.
    """
    parts: list[str] = [f"AGENT DESCRIPTION:\n{description}"]

    if clarifications:
        parts.append("\nCLARIFICATION HISTORY:")
        for item in clarifications:
            parts.append(f"\nRound {item.round}:")
            parts.append(f"  Q: {item.question}")
            parts.append(f"  A: {item.answer}")

    round_count = len(clarifications)
    parts.append(f"\nCURRENT CLARIFICATION ROUND: {round_count}")

    return "\n".join(parts)
