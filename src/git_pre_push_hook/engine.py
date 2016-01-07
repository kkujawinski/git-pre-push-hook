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


class GitWrapper(object):
    def get_min_diff(self, ref1, ref2):
        diff_command = ['git', 'diff',  '-U0', '--no-prefix', ref1 + '..' + ref2]
        return subprocess.check_output(diff_command).rstrip()

    def get_diff_names(self, ref1, ref2):
        diff_command = ['git', 'diff', '--name-only', ref1 + '..' + ref2]
        return subprocess.check_output(diff_command).rstrip()

    def show_content(self, file_path, ref):
        return subprocess.check_output(['git', 'show', ref + ':' + file_path])

    def get_current_ref(self):
        return subprocess.check_output(['git', 'symbolic-ref', 'HEAD']).rstrip()

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
        self.removing_remote = set()

        for commit in changes:
            if commit.local_ref == "(delete)":
                self.removing_remote.add(commit.remote_branch)


class BranchChanges(object):
    def __init__(self, local_ref, local_sha1, remote_ref, remote_sha1, git_wrapper=None):
        if git_wrapper is None:
            git_wrapper = default_git_wrapper
        self.git_wrapper = git_wrapper
        self.local_ref = local_ref
        self.local_sha1 = local_sha1
        self.remote_ref = remote_ref
        self.remote_sha1 = remote_sha1
        self.local_branch = local_ref.split('/')[-1] if '/' in local_ref else None
        self.remote_branch = remote_ref.split('/')[-1] if '/' in remote_ref else None

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

        FILE_NAME_RE = r'\+\+\+ \b(.+)\b'
        CHANGED_LINES_RE = r'@@ -[0-9,]+ \+([0-9]+)(?:,([0-9]+))? @@'
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

            file_content = self.git_wrapper.show_content(file_path, self.local_ref)
            with open(new_file_path, "wb") as fh:
                fh.write(file_content.encode())
            yield new_file_path

    def get_linter_warnings(self):
        try:
            warnings = []
            tmpdir = tempfile.mkdtemp()

            prepared_files = self.prepare_files(target_dir=tmpdir)

            for file_path in prepared_files:
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
