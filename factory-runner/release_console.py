#!/usr/bin/env python3
"""Local operator console. No sockets, credentials or publication commands.

Run under the trusted Runner account with configured workspace directories.
stdout is a sanitized status/receipt summary; errors never include source data.
"""
import argparse
import json
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server
from release_receipt import ReceiptError
from declarative_export import DeclarativeExportError
from rc_fastlane import PreflightError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('projects', 'status', 'prepare', 'operations'))
    parser.add_argument('--project')
    parser.add_argument('--source-sha')
    args = parser.parse_args(argv)
    try:
        if args.action == 'projects':
            result = list(server.listed_projects().values())
        elif args.action == 'operations':
            result = server.recent_operations()
        else:
            if (not args.project or not server.PROJECT_ID.fullmatch(args.project)
                    or not args.source_sha or not server.SHA.fullmatch(args.source_sha)):
                parser.error('project and full source SHA required')
            if args.action == 'status':
                result = server.release_plan(args.project, args.source_sha)
            else:
                profile, _, _ = server.project_workspace(args.project)
                if not ('declarative_rules' in profile or 'declarative_mapping' in profile):
                    raise PreflightError('console_declarative_preparation_only')
                operation_id = str(uuid.uuid4())
                server.record('/api/prepare', None, 'requested', operation_id,
                              actor='local-console')
                try:
                    result = server.prepare_project(args.project, args.source_sha, operation_id)
                except Exception:
                    server.record('/api/prepare', None, 'blocked_policy', operation_id,
                                  actor='local-console')
                    raise
                server.record('/api/prepare', None,
                              'completed_preparation' if result.get('eligible') else 'blocked_policy',
                              operation_id, actor='local-console')
        print(json.dumps({'result': result, 'publication': 'disabled'}, sort_keys=True))
        return 0
    except (ReceiptError, DeclarativeExportError, PreflightError, OSError,
            ValueError, TypeError, RuntimeError):
        print('{"error":"operation_blocked","publication":"disabled"}')
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
