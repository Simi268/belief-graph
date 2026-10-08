from app.events import RevisionEvent


def test_revision_event_creation():

    event = RevisionEvent(
        event_id="REV-001",
        conflict_id="CONFLICT-E1-B1",
        old_belief_id="B1",
        new_belief_id="B2",
        old_action_id="A1",
        new_action_id="A2",
        invalidated_nodes=[
            "B1",
            "A1"
        ],
        reason="API version mismatch"
    )

    assert event.event_id == "REV-001"

    assert (
        event.conflict_id
        == "CONFLICT-E1-B1"
    )

    assert event.old_belief_id == "B1"
    assert event.new_belief_id == "B2"

    assert event.old_action_id == "A1"
    assert event.new_action_id == "A2"

    assert event.invalidated_nodes == [
        "B1",
        "A1"
    ]

    assert event.reason == (
        "API version mismatch"
    )

    assert event.timestamp is not None