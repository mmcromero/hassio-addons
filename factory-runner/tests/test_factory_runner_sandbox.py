"""Negative sandbox tests; never require network, root or HA access."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
import json
import subprocess
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_export as sandbox

class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.target = self.root / "target"
        self.source.mkdir()
        self.target.mkdir()
        (self.source / "export.py").write_text("print('synthetic only')\n")

    def call(self):
        return sandbox.sandbox_export(
            source=self.source, target=self.target, script="export.py",
            sha="a" * 40, verify=False, env={"PATH": os.environ.get("PATH", "")},
            max_output_bytes=1024 * 1024, memory_bytes=128 * 1024 * 1024,
            cpu_seconds=10, elapsed_seconds=2)

    def test_missing_bwrap_fails_closed(self):
        with patch.object(sandbox.shutil, "which", return_value=None):
            with self.assertRaisesRegex(sandbox.SandboxUnavailable, "Bubblewrap"):
                self.call()

    def test_root_execution_fails_closed(self):
        with patch.object(sandbox.shutil, "which", return_value="/usr/bin/bwrap"):
            with patch.object(sandbox.os, "geteuid", return_value=0):
                with self.assertRaisesRegex(sandbox.SandboxUnavailable, "root"):
                    self.call()

    def test_unsafe_exporter_path_fails_closed(self):
        with patch.object(sandbox.shutil, "which", return_value="/usr/bin/bwrap"):
            with patch.object(sandbox.os, "geteuid", return_value=1000):
                with self.assertRaisesRegex(sandbox.SandboxUnavailable, "Invalid script"):
                    sandbox.sandbox_export(
                        source=self.source, target=self.target, script="../passwd",
                        sha="a" * 40, verify=False, env={},
                        max_output_bytes=1024, memory_bytes=1024 * 1024,
                        cpu_seconds=1, elapsed_seconds=1)

    def test_aggregate_size_detection(self):
        (self.target / "a.bin").write_bytes(b"x" * 6)
        (self.target / "b.bin").write_bytes(b"x" * 6)
        self.assertGreater(sandbox._directory_bytes(self.target, 10), 10)

    def test_namespace_is_explicit_not_optional(self):
        # Regression: bwrap --unshare-all uses --unshare-user-try and could
        # silently skip user namespaces on some systems.
        code = (Path(sandbox.__file__)).read_text()
        self.assertIn('"--unshare-user"', code)
        self.assertIn('"--unshare-net"', code)
        self.assertNotIn('"--unshare-all"', code)

    def test_symlink_target_and_script_ancestor_rejected(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.target, target_is_directory=True)
        with self.assertRaisesRegex(sandbox.SandboxUnavailable, 'Symlink'):
            sandbox.sandbox_export(source=self.source, target=alias, script='export.py',
                sha='a'*40, verify=False, env={}, max_output_bytes=1024,
                memory_bytes=1024, cpu_seconds=1, elapsed_seconds=1)
        (self.source/'alias').symlink_to(self.target, target_is_directory=True)
        (self.target/'escape.py').write_text('raise AssertionError("must never run")')
        with patch.object(sandbox.shutil,'which',return_value='/usr/bin/bwrap'):
            with self.assertRaisesRegex(sandbox.SandboxUnavailable,'unsafe'):
                sandbox.sandbox_export(source=self.source,target=self.target,
                    script='alias/escape.py',sha='a'*40,verify=False,env={},
                    max_output_bytes=1024,memory_bytes=1024,cpu_seconds=1,elapsed_seconds=1)

    def test_output_directory_symlinks_rejected_during_scan(self):
        (self.target/'outside').symlink_to(self.source,target_is_directory=True)
        with self.assertRaisesRegex(sandbox.SandboxUnavailable,'symlinks'):
            sandbox._directory_bytes(self.target,1024)

    def test_namespace_denial_never_runs_exporter(self):
        result=type('Result',(),{'returncode':1,'stderr':b'bwrap: namespace: Operation not permitted'})()
        with patch.object(sandbox.shutil,'which',return_value='/usr/bin/bwrap'), \
             patch.object(sandbox.os,'geteuid',return_value=1000), \
             patch.object(sandbox.subprocess,'run',return_value=result), \
             patch.object(sandbox.subprocess,'Popen') as launch:
            with self.assertRaisesRegex(sandbox.SandboxUnavailable,'Operation not permitted'):
                self.call()
            launch.assert_not_called()

    def test_namespace_success_alone_never_runs_project_code(self):
        result=type('Result',(),{'returncode':0,'stderr':b''})()
        with patch.object(sandbox.shutil,'which',return_value='/usr/bin/bwrap'), patch.object(sandbox.os,'geteuid',return_value=1000), patch.object(sandbox.subprocess,'run',return_value=result), patch.object(sandbox.subprocess,'Popen') as launch:
            with self.assertRaisesRegex(sandbox.SandboxUnavailable,'Aggregate sandbox isolation'):
                self.call()
            launch.assert_not_called()

    def test_fresh_helper_session_and_cleanup_without_preexec(self):
        (self.target/'.git').mkdir()
        process=type('Process',(),{'returncode':0,'pid':987654,'poll':lambda self:0})()
        result=type('Result',(),{'returncode':0,'stderr':b''})()
        with patch.object(sandbox.shutil,'which',return_value='/usr/bin/bwrap'), \
             patch.object(sandbox.os,'geteuid',return_value=1000), \
             patch.object(sandbox.subprocess,'run',return_value=result), \
             patch.object(sandbox,'_require_aggregate_isolation'), \
             patch.object(sandbox.subprocess,'Popen',return_value=process) as launch, \
             patch.object(sandbox.os,'killpg') as kill:
            self.call()
        self.assertTrue(launch.call_args.kwargs['start_new_session'])
        self.assertNotIn('preexec_fn',launch.call_args.kwargs)
        self.assertIn('--exec-limited',launch.call_args.args[0])
        argv=launch.call_args.args[0]
        self.assertEqual(argv[3],'--bootstrap-limited')
        self.assertIn('/runner/sandbox_export.py',argv)
        location=argv.index(str(self.target/'.git'))
        self.assertEqual(argv[location-1],'--ro-bind')
        self.assertEqual(argv[location+1],'/target/.git')
        kill.assert_called_once_with(987654,sandbox.signal.SIGKILL)

    def test_special_output_files_rejected(self):
        os.mkfifo(self.target/'pipe')
        with self.assertRaisesRegex(sandbox.SandboxUnavailable,'special files'):
            sandbox._directory_bytes(self.target,1024)

    def test_unreadable_output_is_not_counted_as_empty(self):
        def denied(*args,**kwargs):
            kwargs['onerror'](PermissionError('synthetic inaccessible output'))
        with patch.object(sandbox.os,'walk',side_effect=denied):
            with self.assertRaisesRegex(sandbox.SandboxUnavailable,'cannot be inspected'):
                sandbox._directory_bytes(self.target,1024)

    def test_real_child_rlimits_are_applied_without_root(self):
        code='import json,os,resource;print(json.dumps({"uid":os.geteuid(),"limits":{k:resource.getrlimit(getattr(resource,k))[1] for k in ["RLIMIT_CPU","RLIMIT_AS","RLIMIT_FSIZE","RLIMIT_NOFILE","RLIMIT_NPROC","RLIMIT_CORE"]}}))'
        kwargs={'user':65534,'group':65534,'extra_groups':[]} if os.geteuid()==0 else {}
        # This synthetic stdlib command tests the internal resource helper only;
        # it is deliberately separate from the mandatory exporter sandbox proof.
        r=subprocess.run([sys.executable,'-I',sandbox.__file__,'--exec-limited',
            '2',str(128*1024*1024),str(1024*1024),'/usr/bin/python3','-c',code],
            text=True,capture_output=True,timeout=10,
            env={'PATH':os.environ.get('PATH','')},**kwargs)
        self.assertEqual(r.returncode,0,r.stderr)
        report=json.loads(r.stdout);self.assertNotEqual(report['uid'],0)
        for key,value in {'RLIMIT_CPU':2,'RLIMIT_AS':128*1024*1024,
            'RLIMIT_FSIZE':1024*1024,'RLIMIT_NOFILE':128,'RLIMIT_NPROC':32,'RLIMIT_CORE':0}.items():
            self.assertLessEqual(report['limits'][key],value)

    def test_only_nproc_is_deferred_during_trusted_namespace_bootstrap(self):
        with patch.object(sandbox.resource,'getrlimit',return_value=(-1,-1)), \
             patch.object(sandbox.resource,'setrlimit') as limit:
            sandbox._limits(2,128*1024*1024,1024*1024,process_limit=False)
            keys=[call.args[0] for call in limit.call_args_list]
            self.assertNotIn(sandbox.resource.RLIMIT_NPROC,keys)
            for key in (sandbox.resource.RLIMIT_CPU,sandbox.resource.RLIMIT_AS,
                        sandbox.resource.RLIMIT_FSIZE,sandbox.resource.RLIMIT_NOFILE,
                        sandbox.resource.RLIMIT_CORE):
                self.assertIn(key,keys)
            limit.reset_mock()
            sandbox._limits(2,128*1024*1024,1024*1024)
            limit.assert_any_call(sandbox.resource.RLIMIT_NPROC,(32,32))

if __name__ == "__main__":
    unittest.main()
