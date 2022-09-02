from pathlib import Path
import re

CLEAR_MARK = 'TODO: CODE HERE'
MARK_REGEXP = re.compile(rf'{CLEAR_MARK}(.|\s)*?{CLEAR_MARK}')


def clear_gold_solution(filename: Path) -> None:
    """Cut the marked source code from the gold solution inplace"""

    with open(filename, 'r') as f:
        content = f.read()

    content = re.sub(MARK_REGEXP, CLEAR_MARK, content)

    with open(filename, 'w') as f:
        f.write(content)
