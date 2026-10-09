"""Export the FastAPI OpenAPI contract as reproducible D2 evidence."""

import json
from pathlib import Path

from boreal_marche.api.app import create_app


def main() -> int:
    output = Path("reports/d2/openapi.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(create_app().openapi(), indent=2), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
