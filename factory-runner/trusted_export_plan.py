"""Plan-only Git tree exporter. Never executes source code, copies or publishes.

Input metadata and project rules are untrusted until validated. This module is
an experimental planning core, not a replacement for the approved exporter.
"""
import re


class PlanBlocked(ValueError):
    pass


def _path(value):
    if not isinstance(value, str) or not value or len(value) > 240:
        raise PlanBlocked('invalid_path')
    if value.startswith('/') or '\\' in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise PlanBlocked('invalid_path')
    segments = value.split('/')
    if any(s in ('', '.', '..', '.git') for s in segments) or ':' in segments[0]:
        raise PlanBlocked('invalid_path')
    return value


def plan_files(entries, rules, *, max_files, max_file_bytes, max_total_bytes):
    """Calculate a plan from Git metadata; rejects symlinks and shared writes.

    A caller must independently verify the Git SHA, blob sizes and content.
    This function does not open Git, inspect the working tree or write files.
    """
    if not all(type(x) is int and 0 < x <= 2**40 for x in (max_files, max_file_bytes, max_total_bytes)):
        raise PlanBlocked('invalid_budget')
    if not isinstance(rules, dict) or set(rules) != {'prefix', 'include_prefixes', 'include_suffixes', 'exact', 'allowed_shared_paths'}:
        raise PlanBlocked('invalid_rules')
    prefix = rules['prefix']
    if not isinstance(prefix, str) or not prefix.endswith('/'):
        raise PlanBlocked('invalid_prefix')
    _path(prefix[:-1])
    if prefix.split("/", 1)[0].startswith("."):
        raise PlanBlocked("reserved_destination_prefix")
    include_prefixes = rules['include_prefixes']
    include_suffixes = rules['include_suffixes']
    exact = rules['exact']
    allowed_shared = rules['allowed_shared_paths']
    if (not isinstance(include_prefixes, list) or not isinstance(include_suffixes, list)
            or not isinstance(exact, dict) or not isinstance(allowed_shared, list)):
        raise PlanBlocked('invalid_rules')
    for item in include_prefixes:
        if not isinstance(item, str) or not item.endswith('/'):
            raise PlanBlocked('invalid_rules')
        _path(item[:-1])
    for item in include_suffixes:
        if not isinstance(item, dict) or set(item) != {'prefix', 'suffix'}:
            raise PlanBlocked('invalid_rules')
        p, suffix = item['prefix'], item['suffix']
        if not isinstance(p, str) or not p.endswith('/') or not isinstance(suffix, str) or not re.fullmatch(r'\.[A-Za-z0-9._-]{1,32}', suffix):
            raise PlanBlocked('invalid_rules')
        _path(p[:-1])
    exact = {_path(src): _path(dest) for src, dest in exact.items()}
    allowed_shared = {_path(p) for p in allowed_shared}
    if not isinstance(entries, list):
        raise PlanBlocked('invalid_tree')
    seen_src, seen_dest, planned, total = set(), set(), [], 0
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'path', 'type', 'mode', 'size'}:
            raise PlanBlocked('invalid_tree')
        source = _path(entry['path'])
        if source in seen_src:
            raise PlanBlocked('duplicate_git_path')
        seen_src.add(source)
        match = (source in exact or any(source.startswith(x) for x in include_prefixes)
                 or any(source.startswith(x['prefix']) and source.endswith(x['suffix']) for x in include_suffixes))
        if not match:
            continue
        if entry['type'] != 'blob' or entry['mode'] not in ('100644', '100755'):
            raise PlanBlocked('symlink_submodule_or_special_file')
        size = entry['size']
        if type(size) is not int or size < 0 or size > max_file_bytes:
            raise PlanBlocked('file_budget_exceeded')
        dest_rel = exact.get(source, source)
        dest = _path(dest_rel if (dest_rel.startswith(prefix) or dest_rel in allowed_shared) else prefix + dest_rel)
        if not (dest.startswith(prefix) or dest in allowed_shared):
            raise PlanBlocked('destination_not_allowed')
        if dest in seen_dest:
            raise PlanBlocked('duplicate_destination')
        seen_dest.add(dest)
        total += size
        if len(planned) + 1 > max_files or total > max_total_bytes:
            raise PlanBlocked('aggregate_budget_exceeded')
        planned.append({'source': source, 'destination': dest, 'bytes': size})
    if not set(exact).issubset(seen_src):
        raise PlanBlocked('missing_required_source')
    return {'mode': 'plan_only', 'files': sorted(planned, key=lambda x: x['destination']),
            'total_bytes': total, 'published': False,
            'requires_shared_path_approval': any(item['destination'] in allowed_shared for item in planned)}
