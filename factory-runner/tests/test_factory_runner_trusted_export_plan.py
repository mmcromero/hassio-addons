import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trusted_export_plan import plan_files, PlanBlocked

RULES = {
    'prefix':'pager-virtual/',
    'include_prefixes':['src/', 'tests/fixtures/'],
    'include_suffixes':[{'prefix':'tests/', 'suffix':'.test.js'}],
    'exact':{'package.json':'package.json', 'README.md':'README.md'},
    'allowed_shared_paths':[],
}

def e(path, size=5, mode='100644', kind='blob'):
    return {'path':path, 'size':size, 'type':kind, 'mode':mode}

class PlanTests(unittest.TestCase):
    def plan(self, entries, rules=RULES, **kwargs):
        return plan_files(entries, rules, max_files=kwargs.get('max_files',20),max_file_bytes=kwargs.get('max_file_bytes',100), max_total_bytes=kwargs.get('max_total_bytes',300))

    def test_valid_subset_plan_and_no_side_effect(self):
        result=self.plan([e('README.md'),e('package.json'),e('src/a.js'),e('tests/x.test.js'),e('tests/private.txt')])
        self.assertEqual(result['mode'], 'plan_only')
        self.assertFalse(result['published'])
        self.assertFalse(result['requires_shared_path_approval'])
        self.assertEqual([x['destination'] for x in result['files']], ['pager-virtual/README.md','pager-virtual/package.json','pager-virtual/src/a.js','pager-virtual/tests/x.test.js'])
    def test_reject_traversal_even_when_not_selected(self):
        with self.assertRaises(PlanBlocked): self.plan([e('README.md'),e('package.json'),e('x/../../secret')])
    def test_reject_selected_symlink(self):
        with self.assertRaises(PlanBlocked): self.plan([e('README.md'),e('package.json'),e('src/link', mode='120000')])
    def test_reject_selected_submodule(self):
        with self.assertRaises(PlanBlocked): self.plan([e('README.md'),e('package.json'),e('src/other',mode='160000',kind='commit')])
    def test_missing_required_source(self):
        with self.assertRaises(PlanBlocked): self.plan([e('README.md')])
    def test_duplicate_source(self):
        with self.assertRaises(PlanBlocked): self.plan([e('README.md'),e('README.md'),e('package.json')])
    def test_duplicate_destination(self):
        rules={**RULES, 'exact':{'README.md':'same','package.json':'same'}}
        with self.assertRaises(PlanBlocked): self.plan([e('README.md'),e('package.json')],rules)
    def test_file_limit(self):
        with self.assertRaises(PlanBlocked): self.plan([e('README.md',101),e('package.json')])
    def test_total_limit(self):
        with self.assertRaises(PlanBlocked): self.plan([e('README.md',90),e('package.json',90),e('src/test',90)],max_total_bytes=200)
    def test_exact_outside_prefix_not_allowed(self):
        rules={**RULES,'exact':{'README.md':'../outside','package.json':'package.json'}}
        with self.assertRaises(PlanBlocked): self.plan([e('README.md'),e('package.json')],rules)
    def test_budget_boolean_not_integer(self):
        with self.assertRaises(PlanBlocked): self.plan([e('README.md'),e('package.json')],max_file_bytes=True)
    def test_reject_reserved_prefix(self):
        rules={**RULES,'prefix':'.github/'}
        with self.assertRaises(PlanBlocked): self.plan([e('README.md'),e('package.json')],rules)
    def test_not_enter_host_path(self):
        rules={**RULES,'prefix':'/tmp/out/'}
        with self.assertRaises(PlanBlocked): self.plan([e('README.md'),e('package.json')],rules)

if __name__=='__main__': unittest.main()
