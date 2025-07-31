
import re
import argparse
import sys
from pathlib import Path

def parse_mix_exs(content):
    """
    Parses the content of a mix.exs file to extract dependencies.
    It looks for the `deps` function and extracts the dependency names.
    """
    deps_pattern = re.compile(r"""
        defp\s+deps\s+do
        \s+
        \[
        (.*?)
        \]
        \s+
        end
    """, re.DOTALL | re.VERBOSE)

    deps_content_match = deps_pattern.search(content)
    if not deps_content_match:
        return []

    deps_content = deps_content_match.group(1)
    dep_pattern = re.compile(r'\{\s*:(\w+)')
    dependencies = dep_pattern.findall(deps_content)
    return dependencies

def parse_mix_lock(content):
    """
    Parses the content of a mix.lock file to extract dependency versions.
    It returns a dictionary mapping dependency names to their versions.
    """
    # This pattern is designed to match the structure of a mix.lock file,
    # capturing the dependency name and its version.
    # e.g., "phoenix": {:hex, :phoenix, "1.7.12", ...}
    lock_pattern = re.compile(r'"(\w+)":\s*\{:hex,\s*:\w+,\s*"([^"]+)"')
    matches = lock_pattern.findall(content)

    dep_versions = {}
    for dep_name, version in matches:
        dep_versions[dep_name] = version

    return dep_versions

def main():
    parser = argparse.ArgumentParser(description="Generate a script to build RAG data for Elixir dependencies.")
    parser.add_argument("mix_file", help="Path to the mix.exs file.")
    args = parser.parse_args()

    mix_file_path = Path(args.mix_file)
    if not mix_file_path.is_file():
        print(f"Error: File not found at {mix_file_path}")
        return

    mix_lock_path = mix_file_path.parent / "mix.lock"
    if not mix_lock_path.is_file():
        print(f"Error: mix.lock not found in the same directory as {mix_file_path.name}")
        return

    with open(mix_file_path, "r") as f:
        mix_exs_content = f.read()

    with open(mix_lock_path, "r") as f:
        mix_lock_content = f.read()

    dependencies = parse_mix_exs(mix_exs_content)
    versions = parse_mix_lock(mix_lock_content)

    print("#!/bin/bash")
    print("# Auto-generated script to build RAG data for Elixir dependencies")
    print("")

    for dep in dependencies:
        if dep in versions:
            version = versions[dep]
            print(f"uv run python rag_builder.py build {dep} {version}")
        else:
            print(f"# Dependency '{dep}' not found in mix.lock, skipping.", file=sys.stderr)


if __name__ == "__main__":
    main()
