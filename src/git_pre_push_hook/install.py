import argparse
import os
import stat
import subprocess
import sys


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--force', action='store_true', default=False)
    args = parser.parse_args(args)

    git_dir = subprocess.check_output(['git', 'rev-parse', '--git-dir'])
    hook_file_path = os.path.join(
        os.path.abspath(git_dir.strip()), 'hooks', 'pre-push'
    )

    if not args.force:
        if os.path.exists(hook_file_path):
            sys.stderr.write('error: pre-push hook already exists at %s\n\n' % hook_file_path)
            parser.print_help()
            sys.exit(2)

    with open(hook_file_path, 'w') as fd:
        content = '%s -c "import sys; import git_pre_push_hook.hook; sys.exit(git_pre_push_hook.hook.main())" $@\n' % sys.executable
        fd.write(content)
    os.chmod(hook_file_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)

    sys.stdout.write('pre-push hook installed.\n')
