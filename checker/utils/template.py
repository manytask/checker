from __future__ import annotations

from pathlib import Path
import re

CLEAR_MARK = 'TODO: CODE HERE'
MARK_REGEXP = re.compile(rf'{CLEAR_MARK}(.|\s)*?{CLEAR_MARK}')


def create_template_from_gold_solution(
        filename: Path | str,
        raise_not_found: bool = False,
) -> bool:
    """
    Cut the marked source code from the gold solution inplace

    @param filename: filename to inplace replace code
    @param raise_not_found: raise assertion error if no paired CLEAR_MARK found
    @return: true if successfully replaces and false if not found
    @raises: assertion error if no paired CLEAR_MARK found

    Cut all content between pairs or CLEAR_MARK strings.
    given CLEAR_MARK="YOUR CODE"
    ```python
    a = 1
    # YOUR CODE
    b = 1
    # YOUR CODE
    ```
    You'll get the following result
    ```python
    a = 1
    # YOUR CODE
    ```

    """
    filename = Path(filename)

    assert filename.exists() and filename.is_file(), f'{filename.as_posix()} does not exist'

    with open(filename, 'r') as f:
        content = f.read()

    if not re.search(MARK_REGEXP, content):
        if raise_not_found:
            raise AssertionError(f'Can not find {CLEAR_MARK} pair in {filename.as_posix()}')
        return False

    content = re.sub(MARK_REGEXP, CLEAR_MARK, content)

    with open(filename, 'w') as f:
        f.write(content)

    return True
