try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO
import os
import sys
from collections import namedtuple

from flake8.engine import get_style_guide

flake_config = os.environ.get('LINTER_FLAKE_CONFIG')

if flake_config:
    flake8_style = get_style_guide(config_file=flake_config)
else:
    flake8_style = get_style_guide()

LinterWarning = namedtuple('LinterWarning', ['file_path', 'line_num',
                                             'column_num', 'message'])


def pyflakes(file_path, target_dir=None):
    old_stdout = sys.stdout
    try:
        buffer = StringIO()
        sys.stdout = buffer

        flake8_style.check_files([file_path])

        for line in buffer.getvalue().strip().split('\n'):
            file_path, line_num, column_num, message = line.split(':', 3)
            line_num, column_num = int(line_num), int(column_num)
            message = message.strip()

            if target_dir is not None:
                file_path = os.path.relpath(file_path, target_dir)
            yield LinterWarning(file_path, line_num, column_num, message)
    finally:
        sys.stdout = old_stdout


LINTERS = {
    'py': pyflakes
}
