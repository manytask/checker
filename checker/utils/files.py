from __future__ import annotations

import re
import shutil
from pathlib import Path


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
        source: Path,
        target: Path,
        patterns: list[str] | None = None,
        ignore_patterns: list[str] | None = None,
) -> None:
    """
    Copy files between 2 directories
    @param source: Directory or file to copy from
    @param target: Directory or file to copy to
    @param patterns: Patterns to copy
    @param ignore_patterns: Patterns to ignore during copy
    @return: None
    """
    ignore_patterns = ignore_patterns or []
    target.mkdir(parents=True, exist_ok=True)

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
