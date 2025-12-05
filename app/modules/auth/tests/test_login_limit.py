from datetime import datetime, timedelta, timezone
from app import BLOCK_TIME, MAX_LOGIN_ATTEMPTS


def _post_invalid_login(test_client):
    return test_client.post(
        "/login",
        data={"email": "invalid@example.com", "password": "wrong"},
        follow_redirects=False,
    )

def test_login_not_blocked_before_limit(test_client):
    for _ in range(MAX_LOGIN_ATTEMPTS - 1):
        response = _post_invalid_login(test_client)
        assert response.status_code == 200  

    response = _post_invalid_login(test_client)
    assert response.status_code in (200, 429)  



def test_login_blocked_at_limit(test_client):
    for _ in range(MAX_LOGIN_ATTEMPTS):
        response = _post_invalid_login(test_client)

    assert response.status_code == 429
    assert b"Too many attempts. Try again in 3 minutes." in response.data


def test_login_unblocked_after_block_time(test_client):
    for _ in range(MAX_LOGIN_ATTEMPTS):
        _post_invalid_login(test_client)

    response = _post_invalid_login(test_client)
    assert response.status_code == 429

    with test_client.session_transaction() as sess:
        past_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        sess["block_until"] = past_time.isoformat()

    response = _post_invalid_login(test_client)
    assert response.status_code == 200
    assert b"Invalid credentials" in response.data
