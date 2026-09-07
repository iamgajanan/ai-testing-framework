from __future__ import annotations

import json
import sys

from .engine import LocalEngineAdapter
from .runner import request_from_dict


def main() -> None:
    payload = json.load(sys.stdin)
    request = request_from_dict(payload)
    result = LocalEngineAdapter().execute(request)
    json.dump(_jsonable(result), sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")


def _jsonable(value):
    from enum import Enum

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


if __name__ == "__main__":
    main()
