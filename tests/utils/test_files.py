from __future__ import annotations

import os
from pathlib import Path

import pytest

from checker.utils.files import (
    check_file_contains_regexp,
    check_files_contains_regexp,
    check_folder_contains_regexp,
    copy_files,
    filename_match_patterns,
    get_folders_diff,
    get_folders_diff_except_public,
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

    @pytest.mark.parametrize('regexps,regexps_for_files,contains', [
        (['12'], ['aba.tmp2'], False),
        (['2'], ['aba.tmp2'], True),
        (['12'], ['*b*'], False),
        (['12'], ['*a*'], True),
        (['12'], ['a'], False),
        (['12'], ['*tmp2'], False),
        (['12'], ['**/*a.tmp*'], True),
        (['32'], ['**/*a.tmp*'], True),
        (['32'], ['**/a.tmp*'], False),
        (['.*4.*'], ['a.tmp', 'aba.tmp2'], False),
        (['.*3.*'], ['a.tmp', 'aba.tmp2'], True),
        (['.*3.'], ['a.tmp', 'aba.tmp2'], True),
        (['.*3.'], ['a.tmp'], False),
        (['.*'], None, True),
        (['123'], None, True),
        (['.*'], [], False),
        ([], None, False),
    ])
    def test_check_files_contains_regexp(
            self,
            tmp_path: Path,
            regexps: list[str],
            regexps_for_files: list[str],
            contains: bool
    ) -> None:
        with open(tmp_path / 'a.tmp', 'w') as f1, open(tmp_path / 'aba.tmp2', 'w') as f2:
            f1.write('123')
            f2.write('321')
        assert check_files_contains_regexp(tmp_path, regexps, regexps_for_files) == contains


class TestFolderDiff:
    @pytest.fixture(scope='function')
    def public_folder(self, tmp_path: Path) -> Path:
        public_folder = tmp_path / 'public'
        public_folder.mkdir()
        return public_folder

    @pytest.fixture(scope='function')
    def old_folder(self, tmp_path: Path) -> Path:
        old_folder = tmp_path / 'old'
        old_folder.mkdir()
        return old_folder

    @pytest.fixture(scope='function')
    def new_folder(self, tmp_path: Path) -> Path:
        new_folder = tmp_path / 'new'
        new_folder.mkdir()
        return new_folder

    @staticmethod
    def fill_folder(folder: Path, files: list[str], content: str) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        for file in files:
            with open(folder / file, 'w') as f:
                f.write(content)

    @staticmethod
    def fill_folder_binary_files(folder: Path, files: list[str], content: bytes) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        for file in files:
            with open(folder / file, 'wb') as f:
                f.write(content)

    def test_flat_folders(self, old_folder: Path, new_folder: Path) -> None:
        # same files
        for i in range(10):
            self.fill_folder(old_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)
            self.fill_folder(new_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)

        # completely different files
        different_files = ['a.py', 'b.cpp', 'c.go']
        self.fill_folder(old_folder, different_files, '1\n2\n3\n'*16)
        self.fill_folder(new_folder, different_files, '4\n5\n6\n'*16)

        changed_files = get_folders_diff(old_folder, new_folder)
        assert sorted(changed_files) == sorted(different_files)

    # def test_flat_folders_spaces_diff(self, old_folder: Path, new_folder: Path) -> None:
    #     # same files
    #     for i in range(10):
    #         self.fill_folder(old_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)
    #         self.fill_folder(new_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)
    #
    #     # completely different files
    #     space_different_files = ['a.py', 'b.cpp', 'c.go']
    #     self.fill_folder(old_folder, space_different_files, 'Here lyeth  muche  rychnesse in lytell space.--  John Heywood$')
    #     self.fill_folder(new_folder, space_different_files, '  He relyeth much erychnes  seinly tells pace.  --John Heywood   ^M$')
    #
    #     changed_files = get_folders_diff(old_folder, new_folder)
    #     assert len(changed_files) == 0

    def test_flat_folders_only_same_files(self, old_folder: Path, new_folder: Path) -> None:
        # same files
        for i in range(10):
            self.fill_folder(old_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)
            self.fill_folder(new_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)

        changed_files = get_folders_diff(old_folder, new_folder)
        assert len(changed_files) == 0

    def test_flat_folders_new_and_deleted_files(self, old_folder: Path, new_folder: Path) -> None:
        # same files
        for i in range(10):
            self.fill_folder(old_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)
            self.fill_folder(new_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)

        # deleted files
        deleted_files = ['to_be_deleted_a.py', 'to_be_deleted_b.cpp', 'to_be_deleted_c.go']
        self.fill_folder(old_folder, deleted_files, '1\n2\n3\n'*16)
        # new files
        new_files = ['new_file_a.py', 'new_file_.cpp', 'new_file_.go']
        self.fill_folder(new_folder, new_files, '1\n2\n3\n'*16)

        changed_files = get_folders_diff(old_folder, new_folder)
        assert sorted(changed_files) == sorted(deleted_files + new_files)

    # def test_flat_folders_spaces_in_filename(self, old_folder: Path, new_folder: Path) -> None:
    #     # same files
    #     for i in range(10):
    #         self.fill_folder(old_folder, [f'{i} some {i}.py', f'{i} some {i}.cpp', f'{i} some {i}.go'], '1\n2\n3\n'*16)
    #         self.fill_folder(new_folder, [f'{i} some {i}.py', f'{i} some {i}.cpp', f'{i} some {i}.go'], '1\n2\n3\n'*16)
    #
    #     # completely different files
    #     different_files = ['a some a.py', 'b some b.cpp', 'c some c.go']
    #     self.fill_folder(old_folder, different_files, '1\n2\n3\n'*16)
    #     self.fill_folder(new_folder, different_files, '4\n5\n6\n'*16)
    #
    #     changed_files = get_folders_diff(old_folder, new_folder)
    #     assert sorted(changed_files) == sorted(different_files)

    def test_flat_folders_skip_binary_files(self, old_folder: Path, new_folder: Path) -> None:
        # same files
        for i in range(10):
            self.fill_folder(old_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)
            self.fill_folder(new_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)

        # completely different files
        different_files = ['a.py', 'b.cpp', 'c.go']
        self.fill_folder_binary_files(old_folder, different_files, b'\x00'+os.urandom(4)+b'\x00')
        self.fill_folder_binary_files(new_folder, different_files, b'\x00'+os.urandom(4)+b'\x00')

        changed_files = get_folders_diff(old_folder, new_folder, skip_binary=False)
        assert sorted(changed_files) == sorted(different_files)

        changed_files = get_folders_diff(old_folder, new_folder)
        assert len(changed_files) == 0
        changed_files = get_folders_diff(old_folder, new_folder, skip_binary=True)
        assert len(changed_files) == 0

    def test_deep_structure(self, old_folder: Path, new_folder: Path) -> None:
        # same files
        for i in range(10):
            self.fill_folder(old_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)
            self.fill_folder(new_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)

        # changed files in top folder
        different_files = ['a.py', 'b.cpp', 'c.go']
        self.fill_folder(old_folder, different_files, '1\n2\n3\n'*16)
        self.fill_folder(new_folder, different_files, '4\n3\n2\n'*16)

        # changed files in inner folders
        inner_folder_different_files = ['o.py', 'p.cpp', 'q.go']
        self.fill_folder(old_folder / 'inner-folder', inner_folder_different_files, '1\n2\n3\n'*16)
        self.fill_folder(new_folder / 'inner-folder', inner_folder_different_files, '4\n3\n2\n'*16)

        # new inner folder
        new_inner_folder_files = ['t.py', 'r.cpp', 'n.go']
        self.fill_folder(new_folder / 'new-inner-folder', new_inner_folder_files, '1\n2\n3\n'*16)

        changed_files = get_folders_diff(old_folder, new_folder)
        assert len(changed_files) == len(different_files + inner_folder_different_files + new_inner_folder_files)
        assert all(file in changed_files for file in different_files)
        assert all(f'inner-folder/{file}' in changed_files for file in inner_folder_different_files)
        assert all(f'new-inner-folder/{file}' in changed_files for file in new_inner_folder_files)

    def test_deep_structure_skip_folders(self, old_folder: Path, new_folder: Path) -> None:
        # same files
        for i in range(10):
            self.fill_folder(old_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)
            self.fill_folder(new_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)

        # changed files in inner folders
        inner_folder_different_files = ['o.py', 'p.cpp', 'q.go']
        self.fill_folder(old_folder / 'inner-folder', inner_folder_different_files, '1\n2\n3\n'*16)
        self.fill_folder(new_folder / 'inner-folder', inner_folder_different_files, '4\n3\n2\n'*16)

        # changed files in inner folders
        skip_inner_folder_different_files = ['a.py', 'b.cpp', 'c.go']
        self.fill_folder(old_folder / 'skip-inner-folder', skip_inner_folder_different_files, '1\n2\n3\n'*16)
        self.fill_folder(new_folder / 'skip-inner-folder', skip_inner_folder_different_files, '4\n3\n2\n'*16)

        # changed files in inner folders
        git_folder_different_files = ['aa.py', 'bb.cpp', 'cc.go']
        self.fill_folder(old_folder / '.git', git_folder_different_files, '1\n2\n3\n'*16)
        self.fill_folder(new_folder / '.git', git_folder_different_files, '4\n3\n2\n'*16)

        changed_files = get_folders_diff(old_folder, new_folder, exclude_patterns=['.git', 'skip-inner-folder'])
        assert sorted(changed_files) == sorted([f'inner-folder/{i}' for i in inner_folder_different_files])

    def test_flat_public_folder_filtering(self, public_folder: Path, old_folder: Path, new_folder: Path) -> None:
        # same files
        for i in range(10):
            self.fill_folder(old_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)
            self.fill_folder(new_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)
            self.fill_folder(public_folder, [f'{i}.py', f'{i}.cpp', f'{i}.go'], '1\n2\n3\n'*16)

        # new files in public not in old/new
        new_files_in_public = ['new_in_public_a.py', 'new_in_public_b.cpp', 'new_in_public_c.go']
        self.fill_folder(public_folder, new_files_in_public, '1\n2\n3\n'*16)

        # totally new files in new
        new_files_in_new = ['new_in_new_a.py', 'new_in_new_b.cpp', 'new_in_new_c.go']
        self.fill_folder(new_folder, new_files_in_new, '1\n2\n3\n'*16)

        # new in public and transfer in new
        new_files_in_public_and_new = ['new_in_public_and_new_a.py', 'new_in_public_and_new_b.cpp', 'new_in_public_and_new_c.go']
        self.fill_folder(public_folder, new_files_in_public_and_new, '1\n2\n3\n'*16)
        self.fill_folder(new_folder, new_files_in_public_and_new, '1\n2\n3\n'*16)

        # new in public than changes in new
        new_files_in_public_and_new_changed = ['new_in_public_and_new_changed_a.py', 'new_in_public_and_new_changed_b.cpp', 'new_in_public_and_new_changed_c.go']
        self.fill_folder(public_folder, new_files_in_public_and_new_changed, '1\n2\n3\n'*16)
        self.fill_folder(new_folder, new_files_in_public_and_new_changed, '4\n3\n2\n'*16)

        changed_files = get_folders_diff_except_public(public_folder, old_folder, new_folder)
        print('\nchanged_files')
        for i in changed_files:
            print('-', i)
        assert sorted(changed_files) == sorted(new_files_in_new + new_files_in_public_and_new_changed)
