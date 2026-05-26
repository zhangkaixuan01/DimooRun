import json
import sys
from argparse import ArgumentParser
from pathlib import Path
from tempfile import NamedTemporaryFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "server"))

from dimoo_run.server import create_app  # noqa: E402


def main() -> int:
    parser = ArgumentParser(description="Check whether the checked-in OpenAPI schema is current.")
    parser.add_argument(
        "--schema",
        default="openapi/dimoorun.openapi.json",
        help="Path to the checked-in OpenAPI JSON file.",
    )
    args = parser.parse_args()

    schema_path = Path(args.schema)
    current = json.dumps(
        create_app().openapi(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"

    if not schema_path.exists():
        print(f"OpenAPI schema is missing: {schema_path}", file=sys.stderr)
        return 1

    expected = schema_path.read_text(encoding="utf-8")
    if expected == current:
        print(f"OpenAPI schema is current: {schema_path}")
        return 0

    with NamedTemporaryFile("w", suffix=".openapi.json", delete=False, encoding="utf-8") as file:
        file.write(current)
        generated_path = Path(file.name)
    print(
        "OpenAPI schema is out of date. "
        f"Run `uv run python scripts/export_openapi.py` or compare with {generated_path}.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
