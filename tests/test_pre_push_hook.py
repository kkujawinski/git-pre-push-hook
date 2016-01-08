try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO
import os

from git_pre_push_hook.engine import EMPTY_REF
from git_pre_push_hook.hook import main as hook_main
from py._path.local import LocalPath


class MockGitWrapper(object):
    def get_min_diff(self, ref1, ref2):
        assert ref1 != EMPTY_REF
        assert ref2 != EMPTY_REF
        diff_result = '''
diff --git test_file.py test_file.py
index 62f3f3d..c15c4bc 100644
--- test_file.py
+++ test_file.py
@@ -0,0 +1,3 @@
+def add(x , y):
+    return x+ y
+
@@ -2,0 +6,3 @@ def substract(x, y):
+
+def multiply(x, y):
+    return x*y'''
        return diff_result.strip()

    def get_diff_names(self, ref1, ref2):
        assert ref1 != EMPTY_REF
        assert ref2 != EMPTY_REF
        return 'test_file.py'

    def show_content(self, file_path, ref):
        return (LocalPath('tests/mock_repo/') / file_path).read()

    def get_current_ref(self):
        return 'refs/heads/master'


def test_simple():
    buffer = StringIO()
    git_wrapper = MockGitWrapper()
    args = [
        'origin', 
        'git@github.com:kkujawinski/git-pre-push-hook.git'
    ]
    input_lines = [
        'refs/heads/master 8daa9be23f379f9da4bfdbcc2d465dde03c79057 refs/heads/master bb80b602ee831bd38e3221e534d974824d912565\n'
    ]

    hook_main(args, input_lines, stdout=buffer, git_wrapper=git_wrapper, skip_prompt=True)

    expected_output = '''
Linter warnings:
test_file.py:1:10: E203 whitespace before ','
test_file.py:2:13: E225 missing whitespace around operator
test_file.py:4:1: E302 expected 2 blank lines, found 1
test_file.py:5:17: W291 trailing whitespace
test_file.py:7:1: E302 expected 2 blank lines, found 1


Interactive mode not available.
You can ignore linter warnings by running `git push` from command line.
'''

    assert expected_output.strip() == buffer.getvalue().strip()


def test_changed_lines_only():
    buffer = StringIO()
    git_wrapper = MockGitWrapper()
    args = [
        'origin', 
        'git@github.com:kkujawinski/git-pre-push-hook.git'
    ]
    input_lines = [
        'refs/heads/master 8daa9be23f379f9da4bfdbcc2d465dde03c79057 refs/heads/master bb80b602ee831bd38e3221e534d974824d912565\n'
    ]
    os.environ['CHANGED_LINES_ONLY'] = '1'

    hook_main(args, input_lines, stdout=buffer, git_wrapper=git_wrapper, skip_prompt=True)

    expected_output = '''
Linter warnings:
test_file.py:1:10: E203 whitespace before ','
test_file.py:2:13: E225 missing whitespace around operator
test_file.py:4:1: E302 expected 2 blank lines, found 1
test_file.py:7:1: E302 expected 2 blank lines, found 1


Interactive mode not available.
You can ignore linter warnings by running `git push` from command line.
'''

    assert expected_output.strip() == buffer.getvalue().strip()

