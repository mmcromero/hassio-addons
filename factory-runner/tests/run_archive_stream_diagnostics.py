"""Run archive-stream regression methods individually with stable exit-code mapping.

Exit codes 51..(50 + number_of_tests) identify the first failing test in
alphabetical method-name order. 90 means import/setup failure; 91 means no
test methods were discovered. This is a build diagnostic only.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from test_factory_runner_archive_stream import ArchiveStreamTests
except Exception as exc:
    print(f"ARCHIVE_STREAM_DIAGNOSTIC_IMPORT_ERROR={type(exc).__name__}:{exc}", file=sys.stderr, flush=True)
    raise SystemExit(90)

names = sorted(name for name in dir(ArchiveStreamTests) if name.startswith("test_"))
if not names:
    print("ARCHIVE_STREAM_DIAGNOSTIC_NO_TESTS", file=sys.stderr, flush=True)
    raise SystemExit(91)

for index, name in enumerate(names, start=1):
    print(f"ARCHIVE_STREAM_DIAGNOSTIC_INDEX={index} TEST={name}", file=sys.stderr, flush=True)
    suite = unittest.TestSuite([ArchiveStreamTests(name)])
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
    if not result.wasSuccessful():
        print(f"ARCHIVE_STREAM_DIAGNOSTIC_FAILED_INDEX={index} TEST={name}", file=sys.stderr, flush=True)
        raise SystemExit(50 + index)

print(f"ARCHIVE_STREAM_DIAGNOSTIC_PASS count={len(names)}", file=sys.stderr, flush=True)
