import standman.policy

def test_constant_has_default_message_validator():
    """role.constant must define DEFAULT_MESSAGE_VALIDATOR as a callable."""
    role = standman.policy._create_session_policy_role()
    const = role.constant

    # Attribute must exist
    assert hasattr(const, "SENTINELS")

    # It must be dict
    assert isinstance(const.SENTINELS, dict)
    assert "DEFAULT_MESSAGE_VALIDATOR" in const.SENTINELS

    f = const.SENTINELS["DEFAULT_MESSAGE_VALIDATOR"]
    assert callable(f)

    # It must accept arbitrary args and return None
    assert f("tag", 1, x=2) is None
