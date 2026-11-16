#!/usr/bin/env python3
"""Validate Home Assistant add-on registry and manual selection without running builds."""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ".github" / "addon-registry.json"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--addon", help="Manual build selection; must match a registered ID")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if registry.get("schema_version") != 1:
        raise ValueError("Unsupported registry schema")
    addons = registry.get("addons")
    if not isinstance(addons, list) or not addons:
        raise ValueError("Registry must contain add-ons")
    ids, slugs, directories = set(), set(), set()
    for addon in addons:
        addon_id, directory, slug = (addon.get(k) for k in ("id", "directory", "slug"))
        if not all(isinstance(v, str) and v for v in (addon_id, directory, slug)):
            raise ValueError("Missing required registry field")
        if addon_id in ids or slug in slugs or directory in directories:
            raise ValueError("Duplicate add-on ID, slug or directory")
        if pathlib.PurePosixPath(directory).is_absolute() or ".." in pathlib.PurePosixPath(directory).parts or "/" in addon_id:
            raise ValueError("Invalid directory or ID")
        config = ROOT / directory / "config.yaml"
        if not config.is_file():
            raise ValueError(f"Missing config.yaml for {addon_id}")
        # Compare exact slug with manifest, using the same YAML parser as syntax job.
        import yaml
        manifest = yaml.safe_load(config.read_text(encoding="utf-8"))
        if manifest.get("slug") != slug:
            raise ValueError(f"Slug mismatch for {addon_id}")
        arch = manifest.get("arch", [])
        if not isinstance(arch, list) or set(arch) != set(addon.get("architectures", [])):
            raise ValueError(f"Architecture mismatch for {addon_id}")
        if not (ROOT / directory / "Dockerfile").is_file() and not manifest.get("image"):
            raise ValueError(f"Missing Dockerfile/image for {addon_id}")
        ids.add(addon_id); slugs.add(slug); directories.add(directory)
    # Fail closed if any add-on in this shared catalog lacks a registry entry.
    import yaml
    discovered = {p.name for p in ROOT.iterdir() if p.is_dir() and (p / "config.yaml").is_file()}
    if discovered != directories:
        raise ValueError(f"Catalog/registry mismatch: missing={sorted(discovered-directories)} extra={sorted(directories-discovered)}")
    if args.addon and args.addon not in ids:
        raise ValueError(f"Unregistered add-on: {args.addon}")
    print("Registry OK:", ", ".join(sorted(ids)))
    if args.addon:
        print("Selected:", args.addon)

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, json.JSONDecodeError, ImportError) as exc:
        print(f"REGISTRY ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
