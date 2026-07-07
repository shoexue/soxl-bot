from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.server import dashboard


DEFAULT_OUTPUT = ROOT / "frontend" / "public" / "data" / "dashboard.json"


def env_value(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return value


def strict_json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: strict_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [strict_json_safe(item) for item in value]
    return value


def build_static_dashboard_payload() -> dict[str, Any]:
    payload = dashboard()
    payload["static_export"] = {
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source": "reports/export_dashboard_json.py",
        "deploy_workflow": {
            "event": env_value("GITHUB_EVENT_NAME"),
            "repository": env_value("GITHUB_REPOSITORY"),
            "run_id": env_value("GITHUB_RUN_ID"),
            "run_attempt": env_value("GITHUB_RUN_ATTEMPT"),
            "sha": env_value("GITHUB_SHA"),
            "ref_name": env_value("GITHUB_REF_NAME"),
        },
        "paper_bot_workflow": {
            "run_id": env_value("PAPER_BOT_RUN_ID"),
            "run_number": env_value("PAPER_BOT_RUN_NUMBER"),
            "run_attempt": env_value("PAPER_BOT_RUN_ATTEMPT"),
            "status": env_value("PAPER_BOT_RUN_STATUS"),
            "conclusion": env_value("PAPER_BOT_RUN_CONCLUSION"),
            "event": env_value("PAPER_BOT_RUN_EVENT"),
            "head_branch": env_value("PAPER_BOT_HEAD_BRANCH"),
            "created_at": env_value("PAPER_BOT_CREATED_AT"),
            "updated_at": env_value("PAPER_BOT_UPDATED_AT"),
            "url": env_value("PAPER_BOT_HTML_URL"),
        },
    }
    return strict_json_safe(payload)


def export_dashboard_json(output_path: Path = DEFAULT_OUTPUT) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_static_dashboard_payload()
    with output_path.open("w") as file:
        json.dump(payload, file, indent=2, sort_keys=True, allow_nan=False)
        file.write("\n")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the dashboard API payload as static JSON for Pages."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path. Defaults to {DEFAULT_OUTPUT}.",
    )
    args = parser.parse_args()

    output_path = export_dashboard_json(args.output)
    print(f"Wrote dashboard JSON to {output_path}")


if __name__ == "__main__":
    main()
