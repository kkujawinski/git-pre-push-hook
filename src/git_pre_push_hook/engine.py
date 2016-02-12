#!/usr/bin/env python
import os
import os.path
import re
import shutil
import subprocess
import tempfile
from collections import namedtuple

from .linters import LINTERS


try:
    raw_input
except NameError:
    raw_input = input


class HookParserException(Exception):
    pass

Push = namedtuple('Push', ['changes', 'remote_name', 'remote_url',
                           'current_branch', 'removing_remote'])
LinesRange = namedtuple('LinesRange', ['start', 'end'])
EMPTY_REF = 40 * '0'


class GitWrapper(object):
    def get_min_diff(self, ref1, ref2):
        diff_command = ['git', 'diff',  '-U0', '--no-prefix', ref1 + '..' + ref2]
        return subprocess.check_output(diff_command).rstrip()

    def get_diff_names(self, ref1, ref2):
        diff_command = ['git', 'diff', '--name-status', ref1 + '..' + ref2]
        output_with_status = subprocess.check_output(diff_command).rstrip()

        # removing deleted files from list
        output = []
        for line in output_with_status.split('\n'):
            status, file_name = line.split('\t', 1)
            if status == 'D':
                continue
            output.append(file_name)

        return '\n'.join(output)

    def save_content_to_file(self, file_path, ref, file_hander):
        subprocess.check_call(['git', 'show', ref + ':' + file_path], stdout=file_hander)

    def get_current_ref(self):
        return subprocess.check_output(['git', 'symbolic-ref', 'HEAD']).rstrip()

    def get_remote_refs(self, remote_name=''):
        remotes_prefix = 'refs/remotes/' + remote_name
        refs_command = ['git', 'for-each-ref', '--format', '%(refname)', remotes_prefix]
        return subprocess.check_output(refs_command).rstrip().split('\n')

    def get_revs(self, ref):
        return subprocess.check_output(['git', 'rev-list', ref]).rstrip().split()


default_git_wrapper = GitWrapper()


class Push(object):
    def __init__(self, changes, remote_name, remote_url, git_wrapper=None):
        if git_wrapper is None:
            git_wrapper = default_git_wrapper
        self.git_wrapper = git_wrapper

        self.changes = changes
        self.remote_name = remote_name
        self.remote_url = remote_url

        current_ref = self.git_wrapper.get_current_ref()
        self.current_branch = current_ref.split('/')[-1]


class BranchChanges(object):
    def __init__(self, local_ref, local_sha1, remote_ref, remote_sha1, remote_name, git_wrapper=None):
        if git_wrapper is None:
            git_wrapper = default_git_wrapper
        self.git_wrapper = git_wrapper
        self.local_ref = local_ref
        self.local_sha1 = local_sha1

        if remote_sha1 == EMPTY_REF:
            self.remote_sha1 = self.get_remote_fork_point(remote_name)
        else:
            self.remote_ref = remote_ref
            self.remote_sha1 = remote_sha1

    def get_remote_fork_point(self, remote_name):
        remote_branches = self.git_wrapper.get_remote_refs(remote_name)
        all_remote_revs = set.union(*[set(self.git_wrapper.get_revs(ref)) for ref in remote_branches])

        for rev in self.git_wrapper.get_revs(self.local_ref):
            if rev in all_remote_revs:
                return rev

    def get_user_modified_lines(self):
        """
        Output: {file_path: [(line_a_start, line_a_end), (line_b_start, line_b_end)]}

        Lines ranges are sorted and not overlapping
        """
        # I assume that git diff:
        # - doesn't mix diffs from different files,
        # - diffs are not overlapping
        # - diffs are sorted based on line numbers
        output = {}

        FILE_NAME_RE = r'^\+\+\+ (.+)$'
        CHANGED_LINES_RE = r'^@@ -[0-9,]+ \+([0-9]+)(?:,([0-9]+))? @@'
        current_file_name = None

        for line in self.git_wrapper.get_min_diff(self.remote_sha1, self.local_sha1).split('\n'):
            file_name_match = re.match(FILE_NAME_RE, line)
            if file_name_match:
                current_file_name, = file_name_match.groups()
                output[current_file_name] = []
                continue

            line_number_match = re.match(CHANGED_LINES_RE, line)
            if line_number_match:
                assert current_file_name
                if current_file_name == '/dev/null':
                    continue
                line_start, diff_len = line_number_match.groups()
                line_start, diff_len = int(line_start), int(diff_len or 0)
                output[current_file_name].append(LinesRange(line_start, line_start + diff_len))
                continue

        return output

    def prepare_files(self, target_dir):
        """
        Proper version of file needs to be moved to external directory.
        Because: 1. local files can differ from commited, 2. we can push man branches
        """
        diff_names = self.git_wrapper.get_diff_names(self.remote_sha1, self.local_sha1)
        files_modified = diff_names.split('\n')
        extensions = LINTERS.keys()

        for file_path in files_modified:
            extension = file_path.split('.')[-1]
            if extension not in extensions:
                continue

            new_file_path = os.path.join(target_dir, file_path)
            new_dirname = os.path.dirname(new_file_path)
            if not os.path.isdir(new_dirname):
                os.makedirs(new_dirname)

            with open(new_file_path, "wb") as fh:
                self.git_wrapper.save_content_to_file(file_path, self.local_ref, fh)
            yield new_file_path

    def get_linter_warnings(self):
        try:
            warnings = []
            tmpdir = tempfile.mkdtemp()

            for file_path in self.prepare_files(target_dir=tmpdir):
                extension = file_path.split('.')[-1]
                linter = LINTERS[extension]
                warnings.extend(linter(file_path, target_dir=tmpdir))

            return warnings
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _prepare_user_modified_lines_iterators(self, user_modified_lines):
        user_modified_lines_iterators = {}
        for key in user_modified_lines:
            # Thanks to using iterator we are sure, that we iterate over each list
            # maximum once
            iterator = iter(user_modified_lines[key])
            # We cache last item. Predefined item is lower than possible minimum
            last_item = LinesRange(-1, -1)

            user_modified_lines_iterators[key] = {'last': last_item, 'iter': iterator}
        return user_modified_lines_iterators

    def filter_user_modified_lines(self, commit_warnings, user_modified_lines):
        # We assume that commit_warnings are sorted by line numbers
        user_modified_lines_iterators = self._prepare_user_modified_lines_iterators(user_modified_lines)

        for warning in commit_warnings:
            modified_lines = user_modified_lines_iterators[warning.file_path]
            try:
                while True:
                    lines_range = modified_lines['last']
                    if lines_range.start <= warning.line_num <= lines_range.end:
                        yield warning
                        break
                    if lines_range.start > warning.line_num:
                        break
                    modified_lines['last'] = next(modified_lines['iter'])
            except StopIteration:
                pass

    def get_user_warnings(self):
        commit_warnings = self.get_linter_warnings()
        if os.environ.get('CHANGED_LINES_ONLY'):
            user_modified_lines = self.get_user_modified_lines()
            commit_warnings = self.filter_user_modified_lines(commit_warnings, user_modified_lines)
        return commit_warnings
