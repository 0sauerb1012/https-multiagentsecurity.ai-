from __future__ import annotations

import os
from typing import Iterable


def hydrate_runtime_env(keys: Iterable[str]) -> None:
    """Populate runtime env vars from SSM Parameter Store when *_PARAM is set."""

    parameter_names_by_key: dict[str, str] = {}
    for key in keys:
        if os.getenv(key):
            continue
        parameter_name = os.getenv(f"{key}_PARAM", "").strip()
        if parameter_name:
            parameter_names_by_key[key] = parameter_name

    if not parameter_names_by_key:
        return

    import boto3

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
        raise RuntimeError(f"Missing expected SSM parameters for runtime configuration: {joined}")

    for key, parameter_name in parameter_names_by_key.items():
        os.environ[key] = values_by_name[parameter_name]
