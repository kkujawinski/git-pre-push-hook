import itertools
import sys

from .engine import BranchChanges, Push, HookParserException

try:
    raw_input
except NameError:
    raw_input = input


def format_warnings(warnings):
    for warning in warnings:
        yield '%s:%d:%d: %s\n' % warning


def peek(iterable):
    first = next(iterable)
    return first, itertools.chain([first], iterable)


def query_yes_no(question, default="yes", stdout=None):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    if stdout is None:
        stdout = sys.stdout
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            stdout.write("Please respond with 'yes' or 'no' "
                         "(or 'y' or 'n').\n")


def parse_push(args, lines, git_wrapper=None):
    remote_name, remote_url = args
    changes = []
    for line in lines:
        try:
            local_ref, local_sha1, remote_ref, remote_sha1 = line.split()
        except ValueError:
            raise HookParserException("Could not parse commit from '{}'\n".format(line))
        if local_ref == '(delete)':
            continue
        changes.append(
            BranchChanges(
                local_ref, local_sha1, remote_ref, remote_sha1,
                remote_name=remote_name, git_wrapper=git_wrapper
            )
        )
    return Push(changes=changes, remote_name=remote_name, remote_url=remote_url, git_wrapper=git_wrapper)


def main(args=None, input_lines=None, stdout=None, git_wrapper=None, skip_prompt=False):
    if args is None:
        args = sys.argv[1:]
    if input_lines is None:
        input_lines = sys.stdin.readlines()
    if stdout is None:
        stdout = sys.stdout

    push = parse_push(args, input_lines, git_wrapper=git_wrapper)
    many_refs = len(push.changes) > 1
    any_warning = False

    for commit in push.changes:
        try:
            commit_warnings = commit.get_user_warnings()
        except HookParserException as e:
            stdout.write(
                'Linting skipped for %s due the hook input parsing error : %s.\n' % (commit.local_ref, str(e))
            )

        try:
            _, commit_warnings = peek(iter(commit_warnings))
        except StopIteration:
            continue
        else:
            any_warning = True

        stdout.write('Linter warnings')
        if many_refs:
            stdout.write('(%s)' % commit.local_ref)
        stdout.write(':\n')

        stdout.writelines(format_warnings(commit_warnings))
        stdout.write('\n')

    if any_warning:
        try:
            old_stdin = sys.stdin
            if skip_prompt:
                raise IOError()
            sys.stdin = open('/dev/tty')
            ignore_warnings = query_yes_no('Do you want ignore linting warnings?', default='no')
        except (IOError, EOFError):
            stdout.write('\nInteractive mode not available.\n')
            stdout.write('You can ignore linter warnings by running `git push` from command line.\n')
            return 1
        else:
            if ignore_warnings:
                stdout.write('Linter warnings ignored. Continuing pushing changes.\n')
            else:
                stdout.write('Pushing changes aborted.\n')
                return 1
        finally:
            sys.stdin = old_stdin
    elif push.changes:
        stdout.write('Congratulations! No linter warnings found.\n')
    return 0
