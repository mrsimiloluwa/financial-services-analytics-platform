"""Safe dbt profile bootstrapper generating an environment-variable-driven profiles.yml."""

import argparse
from pathlib import Path

DEFAULT_PROFILES_DIR = Path("/tmp/dbt_profiles")

PROFILES_TEMPLATE = """enterprise_ai_analytics_platform:
  target: dev
  outputs:
    dev:
      type: postgres
      host: "{{ env_var('POSTGRES_HOST') }}"
      port: "{{ env_var('POSTGRES_PORT') | int }}"
      user: "{{ env_var('POSTGRES_USER') }}"
      password: "{{ env_var('POSTGRES_PASSWORD') }}"
      dbname: "{{ env_var('POSTGRES_DB') }}"
      schema: analytics
      threads: 4
    test:
      type: postgres
      host: "{{ env_var('POSTGRES_HOST') }}"
      port: "{{ env_var('POSTGRES_PORT') | int }}"
      user: "{{ env_var('POSTGRES_USER') }}"
      password: "{{ env_var('POSTGRES_PASSWORD') }}"
      dbname: "{{ env_var('POSTGRES_TEST_DB', 'analytics_platform_test') }}"
      schema: analytics
      threads: 4
"""


def write_dbt_profile(profiles_dir: Path = DEFAULT_PROFILES_DIR) -> Path:
    """Create a Jinja env_var()-based profiles.yml without hardcoding any credentials."""
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / "profiles.yml"
    profile_path.write_text(PROFILES_TEMPLATE, encoding="utf-8")
    return profile_path


def main() -> None:
    """CLI entrypoint for bootstrapping the temporary dbt profiles.yml."""
    parser = argparse.ArgumentParser(
        description="Generate an environment-variable-driven dbt profiles.yml outside the repo."
    )
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=DEFAULT_PROFILES_DIR,
        help="Target directory for profiles.yml (default: /tmp/dbt_profiles)",
    )
    args = parser.parse_args()
    path = write_dbt_profile(args.profiles_dir)
    print(f"Created environment-variable-driven dbt profile at: {path}")


if __name__ == "__main__":
    main()
