from __future__ import annotations

from pathlib import Path

import pytest

from checker.utils.files import (
    check_file_contains_regexp,
    check_folder_contains_regexp,
    copy_files,
    filename_match_patterns,
)


class TestFilenameMatch:
    @pytest.mark.parametrize('filename,patterns,matched', [
        ('tmp.py', [r'*.py'], True),
        ('tmp.py', [r'123', r'*.py'], True),
        ('tmp.py', [r'123'], False),
    ])
    def test_filename_match(
            self, tmp_path: Path,
            filename: str, patterns: list[str], matched: bool
    ) -> None:
        with open(tmp_path / filename, 'w') as f:
            f.write('123')
        assert filename_match_patterns(tmp_path / filename, patterns) == matched

    @pytest.mark.parametrize('filenames,patterns,ignore_patterns,result_filenames', [
        (['a.tmp'], [r'*'], None, ['a.tmp']),
        (['a.tmp'], [r'b.tmp'], None, []),
        (['a.tmp'], None, [r'*'], []),
        (['a.tmp', 'b.tmp'], [r'b.*'], None, ['b.tmp']),
    ])
    def test_copy_files_flat(
            self, tmp_path: Path,
            filenames: list[str],
            patterns: list[str] | None,
            ignore_patterns: list[str] | None,
            result_filenames: list[str],
    ) -> None:
        src_path = tmp_path / 'src'
        src_path.mkdir()
        dst_path = tmp_path / 'dst'
        dst_path.mkdir()

        for file in filenames:
            with open(src_path / file, 'w') as f:
                f.write('123')

        copy_files(src_path, dst_path, patterns, ignore_patterns)

        assert [f.name for f in dst_path.iterdir()] == result_filenames


class TestFileRegexpSearch:
    @pytest.mark.parametrize('file_content,regexps,contains', [
        ('123\n321', [r'123'], True),
        ('123\n321', [r'1*1'], True),
        ('123\n321', [r'32[23]'], False),
        ('123\n321', [r'abab'], False),
    ])
    def test_file_regexps(self, tmp_path: Path, file_content: str, regexps: list[str], contains: bool) -> None:
        tmp_file = tmp_path / 'file.tmp'
        with open(tmp_file, 'w') as f:
            f.write(file_content)

        assert check_file_contains_regexp(tmp_file, regexps) == contains

    def test_file_regexps_no_file(self, tmp_path: Path) -> None:
        tmp_file = tmp_path / 'not-existed-file.tmp'
        with pytest.raises(AssertionError):
            check_file_contains_regexp(tmp_file, [r'.*'])

    def test_file_regexps_no_regexps(self, tmp_path: Path) -> None:
        tmp_file = tmp_path / 'file.tmp'
        with open(tmp_file, 'w') as f:
            f.write('123')
        assert not check_file_contains_regexp(tmp_file, [])

    def test_file_regexps_empty_file(self, tmp_path: Path) -> None:
        tmp_file = tmp_path / 'empty-file.tmp'
        tmp_file.touch()

        assert check_file_contains_regexp(tmp_file, [r'.*'])
        assert not check_file_contains_regexp(tmp_file, [])

    @pytest.mark.parametrize('files_content,extensions,regexps,contains', [
        ({'1.txt': '123\n321', '2.txt': 'aaa\nbbb'}, ['txt'], [r'123'], True),
        ({'1.txt': '123\n321', '2.tmp': 'aaa\nbbb'}, ['ini', 'tmp', 'txt'], [r'aaa'], True),
        ({'1.tmp': '123\n321', '2.tmp': 'aaa\nbbb'}, ['txt'], [r'123'], False),
        ({'1.txt': '123\n321', '2.txt': 'aaa\nbbb'}, ['txt'], [r'ttt', r'nnn', r'a.*a'], True),
        ({'1.txt': '123\n321', '2.txt': 'aaa\nbbb'}, ['txt'], [r'ac.*b'], False),
    ])
    def test_folder_regexps(
            self,
            tmp_path: Path,
            files_content: dict[str], extensions: list[str], regexps: list[str], contains: bool,
    ) -> None:
        for file_name, file_content in files_content.items():
            with open(tmp_path / file_name, 'w') as f:
                f.write(file_content)

        assert check_folder_contains_regexp(tmp_path, extensions, regexps) == contains

    def test_folder_regexps_no_folder(self, tmp_path: Path) -> None:
        with pytest.raises(AssertionError):
            check_folder_contains_regexp(tmp_path / 'folder-not-exists', ['py', 'tmp'], [r'.*'])

    def test_folder_regexps_no_regexps(self, tmp_path: Path) -> None:
        with open(tmp_path / 'a.tmp', 'w') as f1, open(tmp_path / 'b.tmp', 'w') as f2:
            f1.write('123')
            f2.write('321')
        assert not check_folder_contains_regexp(tmp_path, ['py', 'tmp'], [])

    def test_folder_regexps_empty_folder(self, tmp_path: Path) -> None:
        assert not check_folder_contains_regexp(tmp_path, ['py', 'tmp'], [r'.*'])

    def test_folder_regexps_raise_on_found(self, tmp_path: Path) -> None:
        with open(tmp_path / 'a.tmp', 'w') as f1, open(tmp_path / 'b.tmp', 'w') as f2:
            f1.write('123')
            f2.write('321')

        with pytest.raises(AssertionError):
            check_folder_contains_regexp(tmp_path, ['tmp'], [r'.*'], raise_on_found=True)

        assert not check_folder_contains_regexp(tmp_path, ['tmp'], [r'ttt'], raise_on_found=True)
