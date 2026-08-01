import time

import pytest

from mcp_server.crypto import RequestStateError, mint_request_state, verify_request_state

SECRET = "test-secret-key-for-hmac"


def test_mint_and_verify_roundtrip():
    token = mint_request_state(
        secret=SECRET,
        cluster_id="prod-db-01",
        script_name="V004__drop_legacy_users.sql",
        iat=1_700_000_000,
    )
    payload = verify_request_state(
        token,
        secret=SECRET,
        cluster_id="prod-db-01",
        script_name="V004__drop_legacy_users.sql",
        now=1_700_000_010,
    )
    assert payload.cluster_id == "prod-db-01"
    assert payload.script_name == "V004__drop_legacy_users.sql"


def test_tampered_token_rejected():
    token = mint_request_state(
        secret=SECRET,
        cluster_id="prod-db-01",
        script_name="V004__drop_legacy_users.sql",
    )
    bad = token[:-1] + ("0" if token[-1] != "0" else "1")
    with pytest.raises(RequestStateError, match="HMAC"):
        verify_request_state(
            bad,
            secret=SECRET,
            cluster_id="prod-db-01",
            script_name="V004__drop_legacy_users.sql",
        )


def test_expired_token_rejected():
    now = int(time.time())
    token = mint_request_state(
        secret=SECRET,
        cluster_id="prod-db-01",
        script_name="V004__drop_legacy_users.sql",
        iat=now - 301,
    )
    with pytest.raises(RequestStateError, match="expired"):
        verify_request_state(
            token,
            secret=SECRET,
            cluster_id="prod-db-01",
            script_name="V004__drop_legacy_users.sql",
            now=now,
        )


def test_bind_mismatch_rejected():
    token = mint_request_state(
        secret=SECRET,
        cluster_id="prod-db-01",
        script_name="V004__drop_legacy_users.sql",
    )
    with pytest.raises(RequestStateError, match="does not match"):
        verify_request_state(
            token,
            secret=SECRET,
            cluster_id="other-cluster",
            script_name="V004__drop_legacy_users.sql",
        )
