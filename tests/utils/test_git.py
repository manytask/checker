from pathlib import Path

from checker.utils import get_tracked_files_list


ROOT_DIR = Path(__file__).parent.parent.parent


class TestGitStats:

    def test_get_tracked_files_list(self) -> None:
        current_file = Path(__file__).absolute().relative_to(ROOT_DIR)
        main_file = (ROOT_DIR / 'checker' / '__main__.py').absolute().relative_to(ROOT_DIR)
        git_tracked_files = get_tracked_files_list(ROOT_DIR)

        assert len(git_tracked_files) > 0
        assert str(current_file) in git_tracked_files
        assert str(main_file) in git_tracked_files
