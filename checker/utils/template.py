from __future__ import annotations

import re
from pathlib import Path


PRECOMPILED_REGEXPS = {}


def cut_marked_code_from_string(
        content: str,
        clear_mark: str | tuple[str, str],
        clear_mark_replace: str,
        raise_not_found: bool = False,
) -> str:
    """
    Cut the marked source code from the gold solution inplace

    @param content: code to inplace replace code
    @param clear_mark: string or (string, string) to cut from gold solution
    @param clear_mark_replace: string to replace cut code
    @param raise_not_found: raise assertion error if no paired <clear_mark> found
    @return: clear content or original content if no <clear_mark> found
    @raises: assertion error if no paired CLEAR_MARK found

    Cut all content between pairs or CLEAR_MARK strings.
    given clear_mark="YOUR CODE" or clear_mark=("YOUR CODE", "YOUR CODE")
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
    global PRECOMPILED_REGEXPS
    clear_mark_start, clear_mark_end = clear_mark if isinstance(clear_mark, tuple) else (clear_mark, clear_mark)

    cut_regexp = rf'{clear_mark_start}(.|\s)*?{clear_mark_end}'
    if cut_regexp not in PRECOMPILED_REGEXPS:
        PRECOMPILED_REGEXPS[cut_regexp] = re.compile(cut_regexp)

    template_content, replace_count = re.subn(PRECOMPILED_REGEXPS[cut_regexp], clear_mark_replace, content)

    if raise_not_found and replace_count == 0:
        raise AssertionError(f'Can not find "{clear_mark_start}" to "{clear_mark_end}" pair')

    return template_content


def create_template_from_gold_solution(
        source_filename: Path | str,
        target_filename: Path | str | None = None,
        clear_mark: str | tuple[str, str] = 'TODO: CODE HERE',
        clear_mark_replace: str = 'TODO: CODE HERE',
        raise_not_found: bool = False,
) -> bool:
    """
    Cut the marked source code from the gold solution inplace

    @param source_filename: filename to replace code of
    @param target_filename: filename to write replace code, if None - inplace
    @param clear_mark: string or (string, string) to cut from gold solution
    @param clear_mark_replace: string to replace cut code
    @param raise_not_found: raise assertion error if no paired <clear_mark> found
    @return: true if successfully replaces and false if not found
    @raises: assertion error if no paired clear_mark found
    @see: cut_marked_code_from_string
    """
    source_filename = Path(source_filename)
    assert source_filename.exists() and source_filename.is_file(), f'{source_filename.as_posix()} does not exist'

    target_filename = target_filename or source_filename

    with open(source_filename, 'r') as f:
        content = f.read()

    template_content = cut_marked_code_from_string(
        content,
        clear_mark,
        clear_mark_replace,
        raise_not_found=raise_not_found,
    )

    with open(target_filename, 'w') as f:
        f.write(template_content)

    return content != template_content
