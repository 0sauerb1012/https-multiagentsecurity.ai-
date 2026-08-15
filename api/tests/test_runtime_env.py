import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.runtime_env import secret_string_value


def test_secret_string_value_extracts_rds_password_json() -> None:
    secret = '{"username":"researchhub_admin","password":"rotated-password"}'

    assert secret_string_value(secret) == "rotated-password"


def test_secret_string_value_keeps_plain_secret_strings() -> None:
    assert secret_string_value("plain-password") == "plain-password"
