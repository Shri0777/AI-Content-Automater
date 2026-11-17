"""The post lifecycle diagram in docs/ARCHITECTURE.md matches the code."""

from pathlib import Path

from studio.statuses import ALLOWED_TRANSITIONS

DOC = Path(__file__).resolve().parent.parent / "docs" / "ARCHITECTURE.md"


def test_every_allowed_status_change_is_drawn():
    text = DOC.read_text()

    missing = []
    for old_status, new_statuses in ALLOWED_TRANSITIONS.items():
        for new_status in new_statuses:
            if f"    {old_status} --> {new_status}\n" not in text:
                missing.append(f"{old_status} --> {new_status}")
    assert missing == []


def state_diagram_lines():
    """Return the lines of the stateDiagram-v2 block only."""
    text = DOC.read_text()
    block = text.split("stateDiagram-v2", 1)[1].split("```", 1)[0]
    return block.splitlines()


def test_no_status_change_is_drawn_that_the_code_does_not_allow():
    drawn = []
    for line in state_diagram_lines():
        parts = line.strip().split(" --> ")
        if len(parts) == 2 and "[*]" not in line:
            drawn.append((parts[0], parts[1]))

    for old_status, new_status in drawn:
        assert new_status in ALLOWED_TRANSITIONS.get(old_status, []), (
            f"{old_status} --> {new_status}"
        )
