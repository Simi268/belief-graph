from app.models import DependencyType, NodeStatus
from app.sdk import BeliefGraphSDK


def test_sdk_builds_reasoning_chain():
    bg = BeliefGraphSDK()

    bg.belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.9,
    )

    bg.conclusion(
        node_id="C1",
        content="The v1 endpoint can be used",
    )

    bg.plan(
        node_id="P1",
        content="Fetch customer data",
    )

    bg.action(
        node_id="A1",
        content="Call customer API",
    )

    bg.depends_on("B1", "C1", DependencyType.REQUIRES)
    bg.depends_on("C1", "P1", DependencyType.REQUIRES)
    bg.depends_on("P1", "A1", DependencyType.REQUIRES)

    assert bg.status("B1") == NodeStatus.ACTIVE
    assert bg.status("C1") == NodeStatus.ACTIVE
    assert bg.status("P1") == NodeStatus.ACTIVE
    assert bg.status("A1") == NodeStatus.ACTIVE