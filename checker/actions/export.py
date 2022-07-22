import os
import shutil
import subprocess
import uuid
from pathlib import Path

from ..course import CourseConfig, CourseDriver
from ..course.schedule import CourseSchedule
from ..utils.git import setup_repo_in_dir, commit_push_all_repo
from ..utils.glab import get_current_user
from ..utils.print import print_info
from ..utils.files import filename_match_patterns


EXPORT_IGNORE_COMMON_FILE_PATTERNS = ['.git', '*.docker', '.releaser-ci.yml', '.deadlines.yml', '.course.yml']


def _get_enabled_files_and_dirs(course_schedule: CourseSchedule, course_driver: CourseDriver) -> set[Path]:
    # list common staff
    common_files: set[Path] = {
        i for i in course_driver.root_dir.glob('*.*')
        if i.is_file() and not filename_match_patterns(i, EXPORT_IGNORE_COMMON_FILE_PATTERNS)
    }
    course_tools: set[Path] = set()
    if (course_driver.root_dir / 'tools').exists():
        course_tools = {course_driver.root_dir / 'tools'}

    # Started groups and tasks in it
    # started_group_dirs: set[Path] = {
    #     course_driver.get_group_source_dir(group)
    #     for group in course_schedule.get_groups(started=True)
    #     if course_driver.get_group_source_dir(group)
    # }
    started_tasks_dirs: set[Path] = {
        course_driver.get_task_source_dir(task)
        for task in course_schedule.get_tasks(enabled=True, started=True)
        if course_driver.get_task_source_dir(task)
    }

    # list enabled task folders ready for deploy
    started_lectures_dirs: set[Path] = {
        course_driver.get_group_lecture_dir(group)
        for group in course_schedule.get_groups(enabled=True, started=True)
        if course_driver.get_group_lecture_dir(group)
    }
    # list ended groups folders ready for deploy
    ended_solutions_dirs: set[Path] = {
        course_driver.get_group_solution_dir(group)
        for group in course_schedule.get_groups(enabled=True, ended=True)
        if course_driver.get_group_solution_dir(group)
    }

    return {*common_files, *course_tools, *started_tasks_dirs, *started_lectures_dirs, *ended_solutions_dirs}


def _dirs_to_files(files_and_dirs: set[Path]) -> set[Path]:
    # Recursive add all files if we have dirs
    all_files_dirs = set()
    for i in files_and_dirs:
        if i.is_file():
            all_files_dirs.add(i)
        else:
            all_files_dirs.update(i.glob('**/*'))

    return all_files_dirs  # - set(PUBLIC_DIR.glob('.git/**/*'))


def _get_disabled_files(
        enabled_files: set[Path],
        course_driver: CourseDriver,
) -> set[Path]:
    all_files = [
        i for i in course_driver.root_dir.glob('**/*') if i.is_file()
    ]

    return set(all_files) - enabled_files - set(course_driver.root_dir.glob('.git/**/*')) - {course_driver.root_dir}


def export_enabled(
        course_config: CourseConfig,
        course_schedule: CourseSchedule,
        course_driver: CourseDriver,
        *,
        dry_run: bool = False,
) -> None:
    """Expecting state: current head is source, public branch is target (remove with public repo)"""

    files_and_dirs_to_add = _get_enabled_files_and_dirs(course_schedule, course_driver)
    enabled_files = _dirs_to_files(files_and_dirs_to_add)

    # if dry_run:
    print_info('Want to add files: ', color='orange')
    for i in sorted(files_and_dirs_to_add):
        print_info(f'  {i.relative_to(course_driver.root_dir)}')

    tmp_branch = uuid.uuid1()

    if not dry_run:
        subprocess.run(
            f'git checkout -b {tmp_branch} && git reset public',
            encoding='utf-8',
            stdout=subprocess.PIPE,
            shell=True
        )

    disabled_files = _get_disabled_files(enabled_files, course_driver)
    print_info('Want to delete files: ', color='orange')
    for i in sorted(disabled_files):
        print_info(f'  {i.relative_to(course_driver.root_dir)}')

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
        'git status',
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
            f'git add {i.relative_to(course_driver.root_dir).as_posix()}',
            encoding='utf-8',
            stdout=subprocess.PIPE,
            shell=True
        )


def export_public_files(
        export_dir: Path,
        course_config: CourseConfig,
        course_schedule: CourseSchedule,
        course_driver: CourseDriver,
        *,
        dry_run: bool = False,
) -> None:
    current_user = get_current_user()

    service_username = current_user.username  # 'pythonbot'
    git_name = current_user.name  # 'Python Bot'
    git_email = current_user.email  # 'shad.service.python@gmail.com'
    service_token = os.environ['PYTHON_COURSE_REPOS_TOKEN']

    export_dir.mkdir(exist_ok=True, parents=True)

    if dry_run:
        print_info(f'Copy {course_config.gitlab_url}/{course_config.public_repo} repo in {export_dir}')
        print_info('copy files...')
        files_and_dirs_to_add = _get_enabled_files_and_dirs(course_schedule, course_driver)
        for f in sorted(files_and_dirs_to_add):
            relative_filename = str(f.relative_to(course_driver.root_dir))
            print_info(f'  {relative_filename}', color='grey')
        return

    setup_repo_in_dir(
        export_dir,
        f'{course_config.gitlab_url}/{course_config.public_repo}',
        'public',
        service_username=service_username,
        service_token=service_token,
        git_user_email=git_email,
        git_user_name=git_name,
    )

    # remove all files (to delete deleted files)
    deleted_files: set[str] = set()
    for path in export_dir.glob('*'):
        if path.name == '.git':
            continue

        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            print(f'wtf. {path}')

        deleted_files.add(str(path.as_posix()))

    # copy updated files
    print_info('copy files...')
    files_and_dirs_to_add = _get_enabled_files_and_dirs(course_schedule, course_driver)
    for f in sorted(files_and_dirs_to_add):
        relative_filename = str(f.relative_to(course_driver.root_dir))
        print_info(f'  {relative_filename}', color='grey')
        if f.is_dir():
            shutil.copytree(f, export_dir / relative_filename)
        else:
            shutil.copy(f, export_dir / relative_filename)

    added_files: set[str] = set()
    for path in export_dir.glob('*'):
        added_files.add(str(path.as_posix()))

    # files for git add
    commit_push_all_repo(
        export_dir,
        'public',
    )
