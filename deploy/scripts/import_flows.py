"""Load exported flow templates into a client's Langflow instance.

    python deploy/scripts/import_flows.py --url http://localhost:7860 --api-key "$LANGFLOW_API_KEY" flows/templates/*.json

Create the API key in Langflow under Settings → Langflow API Keys.
"""

import argparse
import json
import sys
from pathlib import Path

import httpx

# Instance-specific fields from an export that must not be sent to a different instance.
_INSTANCE_FIELDS = ("id", "user_id", "folder_id", "updated_at", "created_at")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--url", default="http://localhost:7860")
    parser.add_argument("--api-key", required=True)
    args = parser.parse_args()

    failed = 0
    with httpx.Client(base_url=args.url, headers={"x-api-key": args.api_key}, timeout=30) as client:
        for path in args.files:
            flow = json.loads(path.read_text())
            for field in _INSTANCE_FIELDS:
                flow.pop(field, None)
            response = client.post("/api/v1/flows/", json=flow)
            if response.is_success:
                print(f"imported {path.name} -> {response.json().get('id')}")
            else:
                failed += 1
                print(f"FAILED {path.name}: {response.status_code} {response.text[:200]}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
