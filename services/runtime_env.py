from __future__ import annotations

import json
import os
from typing import Iterable


def secret_string_value(secret_string: str, key: str = "password") -> str:
    try:
        payload = json.loads(secret_string)
    except json.JSONDecodeError:
        return secret_string

    if isinstance(payload, dict) and isinstance(payload.get(key), str):
        return payload[key]
    return secret_string


def get_secret_value(secret_arn: str, key: str = "password") -> str:
    import boto3

    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    secret_string = response.get("SecretString")
    if not secret_string:
        raise RuntimeError(f"Secret {secret_arn} does not contain a SecretString value.")
    return secret_string_value(secret_string, key)


def hydrate_runtime_env(keys: Iterable[str]) -> None:
    """Populate runtime env vars from SSM Parameter Store or Secrets Manager references."""

    parameter_names_by_key: dict[str, str] = {}
    secret_arns_by_key: dict[str, str] = {}
    for key in keys:
        if os.getenv(key):
            continue
        parameter_name = os.getenv(f"{key}_PARAM", "").strip()
        if parameter_name:
            parameter_names_by_key[key] = parameter_name
            continue
        secret_arn = os.getenv(f"{key}_SECRET_ARN", "").strip()
        if secret_arn:
            secret_arns_by_key[key] = secret_arn

    if not parameter_names_by_key and not secret_arns_by_key:
        return

    import boto3

    if parameter_names_by_key:
        client = boto3.client("ssm")
        response = client.get_parameters(
            Names=list(parameter_names_by_key.values()),
            WithDecryption=True,
        )
        values_by_name = {item["Name"]: item["Value"] for item in response.get("Parameters", [])}

        missing = [
            parameter_name
            for parameter_name in parameter_names_by_key.values()
            if parameter_name not in values_by_name
        ]
        if missing:
            joined = ", ".join(sorted(missing))
            raise RuntimeError(
                f"Missing expected SSM parameters for runtime configuration: {joined}"
            )

        for key, parameter_name in parameter_names_by_key.items():
            os.environ[key] = values_by_name[parameter_name]

    for key, secret_arn in secret_arns_by_key.items():
        os.environ[key] = get_secret_value(secret_arn)
