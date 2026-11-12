"""Write each service's OpenAPI document to packages/api-client/openapi/ (the
source of the generated TypeScript client). Run from backend/:
    uv run python tools/dump_openapi.py            # write
    uv run python tools/dump_openapi.py --check    # fail if out of date (CI)
realtime and worker both have an `app` package, so each runs in its own process."""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
OUT = HERE.parent / "packages" / "api-client" / "openapi"
SERVICES = {"core": (HERE, "core_api.main"), "realtime": (HERE / "realtime", "app.main"), "worker": (HERE / "worker", "app.main")}
DUMP = "import json,sys; m=__import__(sys.argv[1], fromlist=['app']); print(json.dumps(m.app.openapi(), indent=2, sort_keys=True))"


def spec(name: str) -> str:
    cwd, module = SERVICES[name]
    env = {**os.environ, "APP_ENV": "test", "PYTHONPATH": f"{cwd}{os.pathsep}{HERE}",
           "DATABASE_URL": os.environ.get("DATABASE_URL", "postgresql+asyncpg://x:y@localhost:5432/openapi")}
    out = subprocess.run([sys.executable, "-c", DUMP, module], cwd=cwd, env=env, capture_output=True, text=True, check=True)
    return out.stdout.strip() + "\n"


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    for name in SERVICES:
        text = spec(name)
        path = OUT / f"{name}.json"
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(path.name)
        else:
            OUT.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(HERE.parent)}")
    if stale:
        print(f"OpenAPI changed: regenerate the client (python tools/dump_openapi.py, then pnpm --filter @bhojango/api-client generate): {stale}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
