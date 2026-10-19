from examples.order_processing_recovery import run_example


def test_order_processing_example_recovers_and_verifies_end_to_end():
    result = run_example()

    assert result["failure"]["error"] == "API_VERSION_MISMATCH"
    assert result["recovery"]["selective_recovery"]["status"] == "completed"
    assert result["semantic_values_correct"] is True
    assert result["independent_branch_preserved"] is True
    assert result["verification"]["verified"] is True
    assert result["verification"]["stale_nodes"] == []
    assert result["verification"]["stale_semantic_nodes"] == []
    assert result["verification"]["replacement_action_id"] == "A_SUBMIT_ORDER_V2"
    assert set(result["recomputed_node_ids"]) == {
        "C_ORDER_ELIGIBLE",
        "P_CREATE_ORDER",
    }
    assert "B_SHIPPING_AUTH" in result["preserved_node_ids"]
    assert "C_SHIPPING_READY" in result["preserved_node_ids"]
    assert "P_CREATE_SHIPMENT" in result["preserved_node_ids"]


def test_full_restart_comparison_uses_same_failure_and_is_correct():
    result = run_example()
    comparison = result["comparison"]
    selective = comparison["selective"]
    full_restart = comparison["full_restart"]

    assert comparison["same_failure"] is True
    assert selective["failure"] == full_restart["failure"] == "API_VERSION_MISMATCH"
    assert selective["replacement_action_succeeded"] is True
    assert full_restart["replacement_action_succeeded"] is True
    assert selective["final_correct"] is True
    assert full_restart["final_correct"] is True
    assert selective["processed_node_ids"] == [
        "C_ORDER_ELIGIBLE",
        "P_CREATE_ORDER",
    ]
    assert set(selective["preserved_node_ids"]) == {
        "C_SHIPPING_READY",
        "P_CREATE_SHIPMENT",
    }
    assert set(full_restart["processed_node_ids"]) == {
        "C_ORDER_ELIGIBLE",
        "P_CREATE_ORDER",
        "C_SHIPPING_READY",
        "P_CREATE_SHIPMENT",
    }
    assert full_restart["preserved_node_ids"] == []
    assert result["full_restart"]["verification"]["stale_semantic_nodes"] == []


def test_order_processing_example_cli_prints_comparison(capsys):
    from examples.order_processing_recovery import main

    assert main() == 0
    output = capsys.readouterr().out
    assert "API_VERSION_MISMATCH" in output
    assert "Replacement action succeeded: True" in output
    assert "Stale nodes remaining: none" in output
    assert "Stale semantic nodes remaining: none" in output
    assert "Selective recovery" in output
    assert "Full restart" in output
    assert "Selective preserved: C_SHIPPING_READY, P_CREATE_SHIPMENT" in output
    assert "Full-restart preserved: none" in output
    assert "Recovery verified: True" in output
