"""Trusted Raspberry publication contract; only bytes, never project programs."""
import hashlib
import json
import re
import tempfile
from pathlib import Path
from declarative_export import (safe_path,prepare_declarative,expand_trusted_rules,extend_approved_mapping,write_distribution_provenance,_git,_blob)
from release_receipt import verify_receipt, digest


class PublicationError(Exception):
    """Constant reason code only; never attach remote body, credential or path."""


FIELDS = ('project','source_repository','source_ref','source_sha',
          'distribution_repository','distribution_ref','expected_distribution_sha',
          'package_id','version','profile_sha256','scope','allowed_shared_paths')


def binding(receipt, issue):
    if type(issue) is not int or issue <= 0:
        raise PublicationError('invalid_issue')
    return {**{key:receipt[key] for key in FIELDS}, 'issue':issue,
            'action':'publish', 'receipt_sha256':digest(receipt)}


def git_oid(kind, data):
    return hashlib.sha1(kind.encode()+b' '+str(len(data)).encode()+b'\0'+data).hexdigest()


class ArtifactContract:
    """Profile and issue are image/admin configuration, NEVER receipt authority.

    fresh_preflight reads pinned Git blobs using the existing project's evaluator.
    Preparation and publisher accounts must exclusively own their input stores.
    """
    def __init__(self, profile, issue, fresh_preflight, *, source_checkout, distribution_checkout):
        self.source_checkout=Path(source_checkout)
        self.distribution_checkout=Path(distribution_checkout)
        self.profile = profile
        self.issue = issue
        self.fresh_preflight = fresh_preflight
        if profile.get('mode') is not None:
            raise PublicationError('declarative_profile_required')

    def reproduce(self,receipt):
        """Rebuild trusted recipe from immutable Git objects, independently of receipt."""
        p=self.profile;sha=receipt['source_sha'];source=self.source_checkout
        if _git(source,'rev-parse',sha+':'+p['exporter_path']).decode().strip()!=p['exporter_git_blob_sha']:
            raise PublicationError('trusted_recipe_pin_changed')
        mapping=p.get('declarative_mapping')
        if 'declarative_rules' in p:
            rules=p['declarative_rules']
            mapping=expand_trusted_rules(source,sha,destination_prefix=p['distribution_prefix'],
                    required=rules['required'],optional=rules['optional'],include_prefixes=rules['include_prefixes'],include_suffixes=rules['include_suffixes'])
            mapping=extend_approved_mapping(source,sha,mapping,conditional_groups=rules.get('conditional_groups',[]),
                    shared_optional=rules.get('shared_optional',{}),allowed_shared_paths=p['allowed_shared_paths'],distribution_prefix=p['distribution_prefix'])
        if not mapping:raise PublicationError('trusted_declarative_recipe_required')
        if not {p['package_json_path'],p['manifest_path']}.issubset(set(mapping.values())):
            raise PublicationError('trusted_recipe_missing_version_evidence')
        ci=p.get('declarative_ci')
        if ci:
            _blob(source,sha,ci['patch_source'])
            workflow=_blob(self.distribution_checkout,receipt['expected_distribution_sha'],ci['workflow_path']).decode('utf-8')
            if not all(marker in workflow for marker in ci['compatible_markers']):
                raise PublicationError('trusted_recipe_ci_requires_separate_review')
        with tempfile.TemporaryDirectory(prefix='publisher-reproduce-') as tmp:
            root=Path(tmp)/'bundle'
            bundle=prepare_declarative(source,sha,root,mapping,expected_version=receipt['version'],project=p['id'])
            ci=p.get('declarative_ci')
            write_distribution_provenance(root,bundle,source_repository=p['source_repo'],distribution_prefix=p['distribution_prefix'],
                provenance_path=p['provenance_path'],ci_patch_source=ci['patch_source'] if ci else None,allowed_shared_paths=p['allowed_shared_paths'])
            from release_receipt import inventory
            if inventory(root)!=receipt['files']:raise PublicationError('artifact_not_from_pinned_recipe')

    def current_policy(self,receipt):
        p=self.profile;source=self.source_checkout
        head=_git(source,'rev-parse','--verify',p['source_ref']+'^{commit}').decode().strip()
        policy=json.loads(_blob(source,head,p['package_policy_path']))
        active=policy.get('active_package',{})
        if (policy.get('schema_version')!=1 or policy.get('product')!=p['product']
                or active.get('status')!='open' or active.get('id')!=receipt['package_id']
                or active.get('candidate_version')!=receipt['version']
                or active.get('branches',{}).get(p['source_repo'])!=p['rc_ref'].removeprefix('refs/remotes/origin/')):
            raise PublicationError('current_project_policy_blocked')

    def snapshot(self, root, expected_digest):
        r = verify_receipt(root, expected_digest)
        p = self.profile
        checks = {'project':p['id'], 'source_repository':p['source_repo'],
                  'source_ref':p['source_ref'], 'distribution_repository':p['distribution_repo'],
                  'distribution_ref':p['public_ref'].replace('refs/remotes/origin/','refs/heads/'),
                  'profile_sha256':digest(p), 'scope':p['distribution_prefix'],
                  'allowed_shared_paths':p['allowed_shared_paths']}
        if any(r.get(key) != value for key,value in checks.items()):
            raise PublicationError('trusted_profile_mismatch')
        for key in ('source_sha','expected_distribution_sha'):
            if not isinstance(r.get(key),str) or not re.fullmatch('[0-9a-f]{40}',r[key]):
                raise PublicationError('invalid_sha')
        self.current_policy(r)
        report = self.fresh_preflight(r['source_sha'])
        if (report.get('eligible_for_preparation') is not True or report.get('errors')
                or report.get('source_sha') != r['source_sha']
                or report.get('public_main_sha') != r['expected_distribution_sha']
                or report.get('candidate_version') != r['version']
                or report.get('package_id') != r['package_id']
                or report.get('package_status') != 'open'):
            raise PublicationError('current_project_policy_blocked')
        tests = r.get('tests',{})
        if (tests.get('status') != 'PASS' or tests.get('source_sha') != r['source_sha']
                or not isinstance(tests.get('checks'),list) or not tests['checks']
                or any(not isinstance(c,dict) or type(c.get('exit_code')) is not int
                       or c['exit_code'] != 0 or type(c.get('passed')) is not int
                       or c['passed'] < 1 for c in tests['checks'])):
            raise PublicationError('verified_product_tests_required')
        self.reproduce(r)
        records = {item['path']:item for item in r['files']}
        paths = r.get('artifacts')
        if (not isinstance(paths,list) or not paths or len(paths)>512
                or len(set(paths)) != len(paths)
                or set(paths) != set(records)-{'DECLARATIVE_BUNDLE_MANIFEST.json'}):
            raise PublicationError('invalid_artifact_set')
        files = {}
        for name in paths:
            safe_path(name)
            if not (name.startswith(p['distribution_prefix']) or name in p['allowed_shared_paths']):
                raise PublicationError('path_outside_trusted_scope')
            record = records[name]
            data = (Path(root)/name).read_bytes()
            if record['mode'] not in ('100644','100755') or hashlib.sha256(data).hexdigest()!=record['sha256']:
                raise PublicationError('artifact_changed_during_read')
            files[name] = {'mode':record['mode'], 'type':'blob', 'sha':git_oid('blob',data),
                           'sha256':record['sha256'], 'data':data}
        # Data is now an immutable in-memory snapshot; HTTP never opens a path.
        return r, binding(r,self.issue), files
