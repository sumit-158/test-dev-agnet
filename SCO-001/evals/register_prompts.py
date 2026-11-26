"""Register ``prompts/*.md`` in the MLflow Prompt Registry and set the alias (v1/F-03).

CLI: ``python -m evals.register_prompts --alias production [--only <stem>]`` (run from ``SCO-001/``).
Each prompt is registered as ``<CATALOG>.<SCHEMA>.<file stem>`` with the git short sha as the
commit message; the alias is then moved to the new version.
"""

import argparse
import subprocess
from pathlib import Path

import mlflow

from backend.config import Settings, load_settings

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def git_short_sha() -> str:
    """Short sha of HEAD, or ``"unknown"`` when git is unavailable."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROMPTS_DIR.parent,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def register_prompts(
    settings: Settings,
    alias: str,
    only: str | None = None,
    prompts_dir: Path = PROMPTS_DIR,
) -> list[tuple[str, int]]:
    """Register every prompt file (or only ``<only>.md``); return ``(name, version)`` pairs."""
    paths = sorted(prompts_dir.glob("*.md"))
    if only is not None:
        paths = [p for p in paths if p.stem == only]
        if not paths:
            raise ValueError(f"No prompt file {only}.md in {prompts_dir}")
    commit_message = git_short_sha()
    results: list[tuple[str, int]] = []
    for path in paths:
        name = f"{settings.CATALOG}.{settings.SCHEMA}.{path.stem}"
        prompt = mlflow.genai.register_prompt(
            name=name,
            template=path.read_text(encoding="utf-8"),
            commit_message=commit_message,
        )
        version = int(prompt.version)
        mlflow.genai.set_prompt_alias(name, alias=alias, version=version)
        results.append((name, version))
    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--alias", default=None, help="alias to set (default: PROMPT_ALIAS)")
    parser.add_argument("--only", default=None, help="register only prompts/<stem>.md")
    args = parser.parse_args(argv)
    settings = load_settings()
    alias = args.alias or settings.PROMPT_ALIAS
    try:
        results = register_prompts(settings, alias=alias, only=args.only)
    except ValueError as exc:
        parser.error(str(exc))
    for name, version in results:
        print(f"{name} version={version}")


if __name__ == "__main__":
    main()
