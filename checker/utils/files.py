from __future__ import annotations

import re
import shutil
from pathlib import Path
import subprocess

from .print import print_info


def filename_match_patterns(
        file: Path,
        patterns: list[str],
) -> bool:
    """
    Check if filename match any of patterns given
    @param file: Path object to check
    @param patterns: list of regexp pattern (?)
    @return: True if any of patterns applicable
    """
    for pattern in patterns:
        if file.match(pattern):
            return True
    return False


def copy_files(
        source: Path | None,
        target: Path,
        patterns: list[str] | None = None,
        ignore_patterns: list[str] | None = None,
) -> None:
    """
    Copy files between 2 directories
    @param source: Directory or file to copy from (none to skip)
    @param target: Directory or file to copy to
    @param patterns: Patterns to copy
    @param ignore_patterns: Patterns to ignore during copy
    @return: None
    """
    ignore_patterns = ignore_patterns or []
    target.mkdir(parents=True, exist_ok=True)

    if source is None:
        print_info(f'Warning: Skip copying files from <{source}> to <{target}>')
        return

    ignore_files: list[Path] = sum([
        list(source.glob(ignore_pattern))
        for ignore_pattern in ignore_patterns
    ], [])
    for pattern in (patterns or ['*']):
        for file in source.glob(pattern):
            if file in ignore_files:
                continue
            relative_filename = str(file.relative_to(source))
            source_path = source / relative_filename
            target_path = target / relative_filename
            if file.is_dir():
                copy_files(
                    source_path, target_path,
                    patterns=['*'],
                    ignore_patterns=ignore_patterns,
                )
                continue

            shutil.copyfile(str(source_path), str(target_path))


def check_file_contains_regexp(
        filename: Path,
        regexps: list[str],
) -> bool:
    """
    Check regexps appears in the file
    @param filename: Filename to check
    @param regexps: list of forbidden regexp
    @raise AssertionError: if file does not exist
    @return: True if any of regexp found
    """
    assert filename.exists() and filename.is_file()

    with open(filename, 'r', encoding='utf-8') as f:
        file_content = f.read()

        for regexp in regexps:
            if re.search(regexp, file_content, re.MULTILINE):
                return True

    return False


def check_folder_contains_regexp(
        folder: Path,
        extensions: list[str],
        regexps: list[str],
        raise_on_found: bool = False,
) -> bool:
    """
    Check regexps appears in any file in the folder
    @param folder: Folder to check
    @param extensions: Source files extensions
    @param regexps: list of forbidden regexp
    @param raise_on_found: Raise Error on Found Exception
    @raise AssertionError: if folder or any file does not exist
    @return: True if any of regexp found
    """
    assert folder.exists() and folder.is_dir()

    for source_path in folder.glob('**/*.*'):
        if any(str(source_path).endswith(ext) for ext in extensions):
            if check_file_contains_regexp(source_path, regexps):
                if raise_on_found:
                    raise AssertionError(f'File <{source_path}> contains one of <{regexps}>')
                return True
    return False


def check_files_contains_regexp(
        folder: Path,
        regexps: list[str],
        patterns: list[str] | None = None,
        raise_on_found: bool = False,
) -> bool:
    """
    Check regexps appears in files that matching patterns
    @param folder: Folder to check
    @param regexps: list of forbidden regexp
    @param patterns: list of patterns for file matching
    @param raise_on_found: Raise Error on Found Exception
    @raise AssertionError: if folder or any file does not exist
    @return: True if any of regexp found
    """
    assert folder.exists() and folder.is_dir()
    if patterns is None:
        patterns = ['**/*.*']
    for pattern in patterns:
        for source_path in folder.glob(pattern):
            if check_file_contains_regexp(source_path, regexps):
                if raise_on_found:
                    raise AssertionError(f'File <{source_path}> contains one of <{regexps}>')
                return True
    return False


def get_folders_diff(
        old_folder: Path,
        new_folder: Path,
        skip_binary: bool = True,
        exclude_patterns: list[str] | None = None,
) -> list[str]:
    """
    Return diff files between 2 folders
    @param old_folder: Old folder
    @param new_folder: New folder with some changes files, based on old folder
    @param skip_binary: Skip binary files
    @param exclude_patterns: Exclude files that match pattern
    @return: list of changed files as strings
    """
    # diff docs https://www.gnu.org/software/diffutils/manual/html_node/diff-Options.html
    # -N/--new-file - If one file is missing, treat it as present but empty
    # -w/--ignore-all-space - ignore all spaces and tabs  e.g. if ( a == b)  is equal to if(a==b)
    # -r/--recursive - recursively compare any subdirectories found
    # -q/--brief - report only when files differ
    # --strip-trailing-cr - strip trailing carriage return on input
    # -x/--exclude [pattern] - exclude files that match pattern

    # TODO: check format options to work, or --left-column options
    exclude_args = [f'--exclude={pattern}' for pattern in exclude_patterns] if exclude_patterns else []
    # exclude_args = []
    result = subprocess.run(
        [
            'diff',
            '--brief',
            '--recursive',
            '--ignore-all-space',
            '--new-file',
            '--strip-trailing-cr',
            *exclude_args,
            old_folder.absolute(),
            new_folder.absolute()
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = result.stdout.decode()

    # TODO: make it work with whitespace in filenames

    changed = []
    for line in output.split('\n'):
        if line.startswith('Only in'):
            assert False, 'Will be treated as change due to --new-file option'
        elif line.startswith('Files'):
            _, file1, _, file2, _ = line.split()
            changed.append(Path(file2).relative_to(new_folder))
        elif line.startswith('Binary files'):
            if skip_binary:
                continue
            _, _, file1, _, file2, _ = line.split()
            changed.append(Path(file2).relative_to(new_folder))

    return [str(i) for i in changed]


def get_folders_diff_except_public(
        public_folder: Path,
        old_folder: Path,
        new_folder: Path,
        skip_binary: bool = True,
        exclude_patterns: list[str] | None = None,
) -> list[str]:
    """
    Return diff files between 2 folders except files that are equal to public folder files
    @param public_folder: Public folder
    @param old_folder: Old folder
    @param new_folder: New folder with some changes files, based on old folder
    @param skip_binary: Skip binary files
    @param exclude_patterns: Exclude files that match pattern
    @return: list of changed files as strings
    """

    changed_files_old_new = get_folders_diff(
        old_folder,
        new_folder,
        skip_binary=skip_binary,
        exclude_patterns=exclude_patterns,
    )
    changed_files_public_new = get_folders_diff(
        public_folder,
        new_folder,
        skip_binary=skip_binary,
        exclude_patterns=exclude_patterns,
    )

    # TODO: Remove logging
    print_info(f'\nchanged_files_old_new:', color='grey')
    for i in changed_files_old_new:
        print_info(f'  {i}', color='grey')
    print_info(f'\nchanged_files_public_new:', color='grey')
    for i in changed_files_public_new:
        print_info(f'  {i}', color='grey')

    return [
        str(i)
        for i in set(changed_files_old_new) & set(changed_files_public_new)
    ]
