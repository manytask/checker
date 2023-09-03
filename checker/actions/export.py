from __future__ import annotations

import shutil
from pathlib import Path

from ..course import CourseConfig, CourseDriver
from ..course.schedule import CourseSchedule
from ..utils.files import filename_match_patterns
from ..utils.git import commit_push_all_repo, setup_repo_in_dir
from ..utils.print import print_info


EXPORT_IGNORE_COMMON_FILE_PATTERNS = [
    '.git', '*.docker', '.releaser-ci.yml', '.deadlines.yml', '.course.yml', '.DS_Store', '.venv',
    '.*_cache', '.github', '*.drawio',
]


def _get_enabled_files_and_dirs_private_to_public(
        course_config: CourseConfig,
        course_schedule: CourseSchedule,
        public_course_driver: CourseDriver,
        private_course_driver: CourseDriver,
) -> dict[Path, Path]:
    # Common staff; files only, all from private repo except ignored
    common_files: dict[Path, Path] = {
        i: public_course_driver.root_dir / i.name
        for i in private_course_driver.root_dir.glob('*.*')
        if i.is_file() and not filename_match_patterns(i, EXPORT_IGNORE_COMMON_FILE_PATTERNS)
    }

    # Course docs
    course_docs: dict[Path, Path] = dict()
    if (private_course_driver.root_dir / 'docs').exists():
        course_docs.update({
            private_course_driver.root_dir / 'docs': public_course_driver.root_dir / 'docs',
        })
    if (private_course_driver.root_dir / 'images').exists():
        course_docs.update({
            private_course_driver.root_dir / 'images': public_course_driver.root_dir / 'images',
        })

    # Course tools
    course_tools: dict[Path: Path] = dict()
    if (private_course_driver.root_dir / 'tools').exists():
        course_tools = {
            i: public_course_driver.root_dir / 'tools' / i.name
            for i in (private_course_driver.root_dir / 'tools').glob('*')
            if i.is_dir() or (i.is_file() and not filename_match_patterns(i, EXPORT_IGNORE_COMMON_FILE_PATTERNS))
        }

    # Started tasks: copy template to public repo
    started_tasks_templates_dirs: dict[Path: Path] = {
        private_course_driver.get_task_template_dir(task): public_course_driver.get_task_solution_dir(task, check_exists=False)
        for task in course_schedule.get_tasks(enabled=True, started=True)
    }
    started_tasks_public_tests_dirs: dict[Path: Path] = {
        private_course_driver.get_task_public_test_dir(task): public_course_driver.get_task_public_test_dir(task, check_exists=False)
        for task in course_schedule.get_tasks(enabled=True, started=True)
    }
    started_tasks_common_files: dict[Path: Path] = {
        i: public_course_driver.get_task_dir(task, check_exists=False) / i.name
        for task in course_schedule.get_tasks(enabled=True, started=True)
        for i in private_course_driver.get_task_dir(task).glob('*.*')
    }

    # Lectures for enabled groups (if any)
    started_lectures_dirs: dict[Path: Path] = {
        private_lecture_dir: public_course_driver.get_group_lecture_dir(group, check_exists=False)
        for group in course_schedule.get_groups(enabled=True, started=True)
        if (private_lecture_dir := private_course_driver.get_group_lecture_dir(group)).exists()
    }

    # Reviews for ended groups (if any)
    ended_reviews_dirs: dict[Path: Path] = {
        private_review_dir: public_course_driver.get_group_submissions_review_dir(group, check_exists=False)
        for group in course_schedule.get_groups(enabled=True, ended=True)
        if (private_review_dir := private_course_driver.get_group_submissions_review_dir(group)).exists()
    }

    return {
        **common_files,
        **course_docs,
        **course_tools,
        **started_tasks_templates_dirs,
        **started_tasks_public_tests_dirs,
        **started_tasks_common_files,
        **started_lectures_dirs,
        **ended_reviews_dirs,
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
        public_course_driver: CourseDriver,
        private_course_driver: CourseDriver,
        export_dir: Path,
        *,
        dry_run: bool = False,
) -> None:
    export_dir.mkdir(exist_ok=True, parents=True)

    if dry_run:
        print_info('Dry run. No repo setup, only copy in export_dir dir.', color='orange')

    files_and_dirs_to_add_map: dict[Path, Path] = _get_enabled_files_and_dirs_private_to_public(
        course_config,
        course_schedule,
        public_course_driver,
        private_course_driver,
    )

    if not dry_run:
        if not course_config.gitlab_service_token:
            raise Exception('Unable to find service_token')  # TODO: set exception correct type

        print_info('Setting up public repo...', color='orange')
        print_info(f'  Copy {course_config.gitlab_url}/{course_config.public_repo} repo in {export_dir}')
        print_info(
            f'  username {course_config.gitlab_service_username} \n'
            f'  name {course_config.gitlab_service_name} \n'
            f'  branch {course_config.default_branch} \n',
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

    # remove all files from export_dir (to delete deleted files)
    print_info('Delete all files from old export_dir (keep .git)...', color='orange')
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
    for filename_private, filename_public in sorted(files_and_dirs_to_add_map.items()):
        relative_private_filename = str(filename_private.relative_to(private_course_driver.root_dir))
        relative_public_filename = str(filename_public.relative_to(public_course_driver.root_dir))
        print_info(f'  {relative_private_filename}', color='grey')
        print_info(f'  \t-> {relative_public_filename}', color='grey')

        if filename_private.is_dir():
            shutil.copytree(filename_private, export_dir / relative_public_filename, dirs_exist_ok=True)
        else:
            (export_dir / relative_public_filename).parent.mkdir(exist_ok=True, parents=True)
            shutil.copy(filename_private, export_dir / relative_public_filename)

    if not dry_run:
        # files for git add
        commit_push_all_repo(
            export_dir,
            branch=course_config.default_branch,
        )
