from __future__ import annotations

import shutil
from pathlib import Path

from ..course import CourseConfig, CourseDriver
from ..course.schedule import CourseSchedule
from ..utils.files import filename_match_patterns
from ..utils.git import commit_push_all_repo, setup_repo_in_dir
from ..utils.print import print_info

EXPORT_IGNORE_COMMON_FILE_PATTERNS = [
    '.git', '*.docker', '.releaser-ci.yml', '.deadlines.yml', '.course.yml',
]


def _get_enabled_files_and_dirs(
        course_config: CourseConfig,
        course_schedule: CourseSchedule,
        course_driver: CourseDriver,
) -> set[Path]:
    # Common staff; files only
    common_files: set[Path] = {
        i for i in course_driver.root_dir.glob('*.*')
        if i.is_file() and not filename_match_patterns(i, EXPORT_IGNORE_COMMON_FILE_PATTERNS)
    }

    # Course docs
    course_docs: set[Path] = set()
    if (course_driver.root_dir / 'docs').exists():
        course_docs.update({course_driver.root_dir / 'docs'})
    if (course_driver.root_dir / 'images').exists():
        course_docs.update({course_driver.root_dir / 'images'})

    # Course tools
    course_tools: set[Path] = set()
    if (course_driver.root_dir / 'tools').exists():
        course_tools = {
            i for i in (course_driver.root_dir / 'tools').glob('*')
            if i.is_dir() or (i.is_file() and not filename_match_patterns(i, EXPORT_IGNORE_COMMON_FILE_PATTERNS))
        }

    # Started tasks
    started_tasks_dirs: set[Path] = {
        source_dir
        for task in course_schedule.get_tasks(enabled=True, started=True)
        if (source_dir := course_driver.get_task_source_dir(task))
    }

    # Lectures for enabled groups (if any)
    started_lectures_dirs: set[Path] = {
        lecture_dir
        for group in course_schedule.get_groups(enabled=True, started=True)
        if (lecture_dir := course_driver.get_group_lecture_dir(group))
    }

    # Solutions for ended groups (if any)
    ended_solutions_dirs: set[Path] = {
        solution_dir
        for group in course_schedule.get_groups(enabled=True, ended=True)
        if (solution_dir := course_driver.get_group_solution_dir(group))
    }

    return {
        *common_files,
        *course_docs,
        *course_tools,
        *started_tasks_dirs,
        *started_lectures_dirs,
        *ended_solutions_dirs
    }


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


def export_public_files(
        course_config: CourseConfig,
        course_schedule: CourseSchedule,
        course_driver: CourseDriver,
        export_dir: Path,
        *,
        dry_run: bool = False,
) -> None:
    export_dir.mkdir(exist_ok=True, parents=True)

    if dry_run:
        print_info(f'Copy {course_config.gitlab_url}/{course_config.public_repo} repo in {export_dir}')
        print_info('copy files...')
        files_and_dirs_to_add = _get_enabled_files_and_dirs(course_config, course_schedule, course_driver)
        for f in sorted(files_and_dirs_to_add):
            relative_filename = str(f.relative_to(course_driver.root_dir))
            print_info(f'  {relative_filename}', color='grey')
        return

    if not course_config.gitlab_service_token:
        raise Exception('Unable to find service_token')  # TODO: set exception correct type

    print_info('Setting up public repo...', color='orange')
    print_info(
        f'username {course_config.gitlab_service_username} \n'
        f'name {course_config.gitlab_service_name} \n'
        f'branch {course_config.default_branch} \n',
        color='grey'
    )
    setup_repo_in_dir(
        export_dir,
        f'{course_config.gitlab_url}/{course_config.public_repo}',
        service_username=course_config.gitlab_service_username,
        service_token=course_config.gitlab_service_token,
        git_user_email=course_config.gitlab_service_email,
        git_user_name=course_config.gitlab_service_name,
        branch=course_config.default_branch,
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
    print_info('Copy updated files...', color='orange')
    files_and_dirs_to_add = _get_enabled_files_and_dirs(course_config, course_schedule, course_driver)
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
        branch=course_config.default_branch,
    )
