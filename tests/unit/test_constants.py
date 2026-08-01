from mcp_server.mrtr_types import (
    ENVIRONMENT_TAGS,
    build_confirm_drop_schema,
    is_destructive_script,
    is_valid_environment_tag,
)


def test_environment_tags_allow_list():
    assert ENVIRONMENT_TAGS == ("dev", "staging", "prod")
    assert is_valid_environment_tag("prod")
    assert not is_valid_environment_tag("qa")
    assert not is_valid_environment_tag("PROD")


def test_schema_enum_uses_single_allow_list():
    schema = build_confirm_drop_schema()
    assert schema["properties"]["environment_tag"]["enum"] == list(ENVIRONMENT_TAGS)


def test_destructive_keywords():
    assert is_destructive_script("V004__drop_legacy_users.sql")
    assert is_destructive_script("V004__DESTRUCTIVE_cleanup.sql")
    assert not is_destructive_script("V001__add_index.sql")
