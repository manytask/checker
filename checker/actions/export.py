import shutil
import subprocess
import uuid
from pathlib import Path

from ..course import Course, PUBLIC_DIR
from ..utils.print import print_info
from ..utils.files import file_match_patterns


EXPORT_IGNORE_FILE_PATTERNS = ['*.docker', '.releaser-ci.yml']


def _list_enabled(course: Course) -> set[Path]:

    # list common staff
    common_files = {
        i for i in PUBLIC_DIR.glob('*.*') if i.is_file() and not file_match_patterns(i, EXPORT_IGNORE_FILE_PATTERNS)
    }

    # Started groups and tasks in it
    started_group_dirs: set[Path] = {
        group.public_dir for group in course.get_groups(valid=True, started=True) if group.public_dir.exists()
    }

    # list enabled task folders ready for deploy
    started_lectures_dirs: set[Path] = {
        group.lectures_dir for group in course.get_groups(started=True) if group.lectures_dir.exists()
    }

    # TODO: solutions
    pass

    return {*common_files, *started_group_dirs, *started_lectures_dirs}


def _list_enabled_files(files_and_dirs: set[Path]) -> set[Path]:
    # Recursive add all files if we have dirs
    all_files_dirs = set()
    for i in files_and_dirs:
        if i.is_file():
            all_files_dirs.add(i)
        else:
            all_files_dirs.update(i.glob('**/*'))

    return all_files_dirs - set(PUBLIC_DIR.glob('.git/**/*'))


def _list_disabled_files(enabled_files: set[Path]) -> set[Path]:
    all_files = [
        i for i in PUBLIC_DIR.glob('**/*') if i.is_file()
    ]

    return set(all_files) - enabled_files - set(PUBLIC_DIR.glob('.git/**/*')) - {PUBLIC_DIR}


def export_enabled(course: Course, dry_run: bool = False) -> None:
    """Expecting state: current head is source, public branch is target (remove with public repo)"""

    files_and_dirs_to_add = _list_enabled(course)
    enabled_files = _list_enabled_files(files_and_dirs_to_add)

    # if dry_run:
    print_info('Want to add files: ', color='orange')
    print_info({i for i in files_and_dirs_to_add})

    tmp_branch = uuid.uuid1()

    if not dry_run:
        subprocess.run(
            f'git checkout -b {tmp_branch} && git reset public',
            encoding='utf-8',
            stdout=subprocess.PIPE,
            shell=True
        )

    disabled_files = _list_disabled_files(enabled_files)
    print_info('Want to delete files: ', color='orange')
    print_info({i for i in disabled_files})

    if dry_run:
        return

    # remove files
    for i in disabled_files:
        if i.exists():
            if i.is_file():
                i.unlink(missing_ok=True)
                files_and_dirs_to_add.add(i)
            elif i.is_dir():
                shutil.rmtree(i)
                files_and_dirs_to_add.add(i)

    status = subprocess.run(
        f'git status',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True
    )
    print_info(status.stderr or '')
    print_info(status.stdout, color='grey')
    print_info('---')

    subprocess.run(
        f'git checkout public && git branch -D {tmp_branch}',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True
    )

    # Add files
    for i in files_and_dirs_to_add:
        # print(i.relative_to(MAIN_DIR).as_posix())
        subprocess.run(
            f'git add {i.relative_to(PUBLIC_DIR).as_posix()}',
            encoding='utf-8',
            stdout=subprocess.PIPE,
            shell=True
        )

