from app.environment import DynamicAPIEnvironment


def test_initial_api_version():
    env = DynamicAPIEnvironment()

    assert env.get_api_version() == "v1"


def test_api_version_can_change():
    env = DynamicAPIEnvironment()

    env.set_api_version("v2")

    assert env.get_api_version() == "v2"


def test_call_with_correct_version_succeeds():
    env = DynamicAPIEnvironment()

    result = env.call_api("v1")

    assert result["success"] is True
    assert result["data"] == "customer-data"


def test_call_with_wrong_version_fails():
    env = DynamicAPIEnvironment()

    env.set_api_version("v2")

    result = env.call_api("v1")

    assert result["success"] is False
    assert result["error"] == "API_VERSION_MISMATCH"
    assert result["expected"] == "v2"
    assert result["received"] == "v1"


def test_new_version_call_succeeds_after_environment_change():
    env = DynamicAPIEnvironment()

    env.set_api_version("v2")

    result = env.call_api("v2")

    assert result["success"] is True
    assert result["data"] == "customer-data"