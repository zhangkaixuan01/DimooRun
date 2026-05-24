import json
import sys
from argparse import ArgumentParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "server"))

from dimoo_run.server import create_app  # noqa: E402


def main() -> None:
    parser = ArgumentParser(description="Export the DimooRun OpenAPI schema.")
    parser.add_argument(
        "--output",
        default="openapi/dimoorun.openapi.json",
        help="Path to the OpenAPI JSON output file.",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    schema = create_app().openapi()
    output_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Exported OpenAPI schema to {output_path}")


if __name__ == "__main__":
    main()
