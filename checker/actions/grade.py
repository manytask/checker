from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from ..course import CourseConfig, CourseDriver, CourseSchedule, Group, Task
from ..exceptions import RunFailedError
from ..testers import Tester
from ..utils import get_folders_diff_except_public, get_tracked_files_list
from ..utils.manytask import PushFailedError, push_report
from ..utils.print import print_info, print_task_info


class GitException(Exception):
    pass


def _get_git_changes(
        solution_root: str,
        public_repo_url: str,
        author_name: str | None = None,
        current_commit_sha: str | None = None,
        prev_commit_sha: str | None = None,
        git_changes_type: str = 'log_between_no_upstream',
) -> list[str]:
    """
    :param solution_root: Full path to solutions folder
    :param public_repo_url: Full url to public repo
    :param git_changes_type: one of
        'diff_last', 'diff_between', 'log_between_no_merges', 'log_between_by_author', 'log_between_no_upstream'
    """
    if author_name is None and git_changes_type == 'log_between_by_author':
        git_changes_type = 'log_between_no_merges'

    if prev_commit_sha and set(prev_commit_sha) == {'0'}:  # first commit or merge request
        prev_commit_sha = None

    if 'between' in git_changes_type and (current_commit_sha is None or prev_commit_sha is None):
        print_info('CI_COMMIT_SHA or CI_COMMIT_BEFORE_SHA is wrong pipeline_diff can not be used. '
                   'Using std `git show`')
        print_info(f'CI_COMMIT_SHA: {current_commit_sha}, CI_COMMIT_BEFORE_SHA: {prev_commit_sha}!')
        git_changes_type = 'diff_last'

    changes = []
    if git_changes_type.startswith('diff'):
        if git_changes_type == 'diff_between':
            print_info(f'Looking diff between {prev_commit_sha} and {current_commit_sha}...')
            prev_commit_sha = '' if prev_commit_sha is None else prev_commit_sha
            git_status = subprocess.run(
                f'cd {solution_root} && git diff {prev_commit_sha} {current_commit_sha} --stat --oneline',
                encoding='utf-8',
                stdout=subprocess.PIPE,
                shell=True
            ).stdout
            print_info(git_status)
            changes = git_status.split('\n')[:-2]
        elif git_changes_type == 'diff_last':
            print_info('Looking last commit diff...')
            git_status = subprocess.run(
                f'cd {solution_root} && git show --stat --oneline',
                encoding='utf-8',
                stdout=subprocess.PIPE,
                shell=True
            ).stdout
            print_info(git_status)
            changes = git_status.split('\n')[1:-2]
        else:
            raise GitException(f'Unknown git_changes_type={git_changes_type}')

        changes = [f.rsplit('|', maxsplit=1)[0].strip() for f in changes]

    elif git_changes_type.startswith('log'):
        if git_changes_type == 'log_between_no_merges':
            print_info(f'Looking log between {prev_commit_sha} and {current_commit_sha} without merges...')
            prev_commit_sha = '' if prev_commit_sha is None else prev_commit_sha
            git_status = subprocess.run(
                f'cd {solution_root} && '
                f'git log --pretty="%H" --no-merges {prev_commit_sha or ""}..{current_commit_sha} | '
                f'while read commit_hash; do git show --oneline --name-only $commit_hash'
                f'| tail -n+2; done | sort | uniq',
                encoding='utf-8',
                stdout=subprocess.PIPE,
                shell=True
            ).stdout
            print_info(git_status)
            changes = git_status.split('\n')
        elif git_changes_type == 'log_between_by_author':
            assert isinstance(author_name, str)
            print_info(
                f'Looking log between {prev_commit_sha} and {current_commit_sha} '
                f'by author="{author_name.split(" ")[0]}"...',
            )
            prev_commit_sha = '' if prev_commit_sha is None else prev_commit_sha
            git_status = subprocess.run(
                f'cd {solution_root} && '
                f'git log --pretty="%H" --author="{author_name.split(" ")[0]}"'
                f'{prev_commit_sha or ""}..{current_commit_sha} | '
                f'while read commit_hash; do git show --oneline --name-only $commit_hash '
                f'| tail -n+2; done | sort | uniq',
                encoding='utf-8',
                stdout=subprocess.PIPE,
                shell=True,
            ).stdout
            print_info(git_status)
            changes = git_status.split('\n')
        elif git_changes_type == 'log_between_no_upstream':
            print_info(f'Looking log_between_no_upstream between {prev_commit_sha} and {current_commit_sha} '
                       f'which not in `{public_repo_url}`...')

            result = subprocess.run(
                f'cd {solution_root} && '
                f'git fetch --unshallow &&'
                f'(git remote rm upstream | true) &&'
                f'git remote add upstream {public_repo_url}.git &&'
                f'git fetch upstream',
                encoding='utf-8',
                capture_output=True,
                shell=True
            )
            print_info(result.stderr, color='grey')
            print_info(result.stdout, color='grey')

            print_info('---')

            git_status = subprocess.run(
                f'cd {solution_root} && '
                f'git log --pretty="%H" {prev_commit_sha or ""}..{current_commit_sha} '
                f'--no-merges --not --remotes=upstream | '
                f'while read commit_hash; do git show --oneline --name-only $commit_hash '
                f'| tail -n+2; done | sort | uniq',
                encoding='utf-8',
                stdout=subprocess.PIPE,
                shell=True
            ).stdout
            print_info('Detected changes in the following files:')
            print_info(git_status, color='grey')
            changes = git_status.split('\n')
        else:
            raise GitException(f'Unknown git_changes_type={git_changes_type}')

        changes = [f for f in changes if len(f) > 0]

    return changes


def grade_single_task(
        task: Task,
        tester: Tester,
        course_config: CourseConfig,
        public_course_driver: CourseDriver,
        private_course_driver: CourseDriver,
        user_id: int,
        send_time: datetime,
        inspect: bool = False
) -> bool:
    print_task_info(task.full_name)
    source_dir = public_course_driver.get_task_solution_dir(task)
    reference_config_dir = private_course_driver.get_task_config_dir(task)
    reference_public_tests_dir = private_course_driver.get_task_public_test_dir(task)
    reference_private_tests_dir = private_course_driver.get_task_private_test_dir(task)
    reference_tests_root_dir = private_course_driver.root_dir
    assert source_dir, 'source_dir have to exists'
    assert reference_config_dir, 'reference_config_dir have to exists'
    assert reference_public_tests_dir or reference_private_tests_dir, \
        'reference_public_tests_dir or reference_private_tests_dir have to exists'

    try:
        score_percentage = tester.test_task(
            source_dir,
            reference_config_dir,
            reference_public_tests_dir,
            reference_private_tests_dir,
            reference_tests_root_dir,
            verbose=inspect,
            normalize_output=inspect,
        )
        score = round(score_percentage * task.max_score)
        if score_percentage == 1.:
            print_info(f'\nSolution score is: {score}', color='green')
        else:
            print_info(f'\nSolution score percentage is: {score_percentage}', color='green')
            print_info(f'\nSolution score is: [{task.max_score}*{score_percentage}]={score}', color='green')
        if task.review:
            print_info('\nThis task is "review-able", so, open MR and wait till review.', color='blue')
        elif not inspect:
            use_demand_multiplier = not task.marked
            try:
                if not course_config.manytask_token:
                    raise PushFailedError('Unable to find manytask token')
                files = {
                    path.name: (str(path.relative_to(source_dir)), open(path, 'rb'))
                    for path in source_dir.glob('**/*')
                    if path.is_file()
                }
                username, set_score, result_commit_time, result_submit_time, demand_multiplier = push_report(
                    course_config.manytask_url,
                    course_config.manytask_token,
                    task.name,
                    user_id,
                    score,
                    files=files,
                    send_time=send_time,
                    use_demand_multiplier=use_demand_multiplier,
                )
                print_info(
                    f'Final score for @{username} (according to deadlines and demand): {set_score}',
                    color='blue'
                )
                if demand_multiplier and demand_multiplier != 1:
                    print_info(
                        f'Due to low demand, the task score is multiplied at {demand_multiplier:.4f}',
                        color='grey'
                    )
                if result_commit_time:
                    print_info(f'Commit at {result_commit_time} (are validated to Submit Time)', color='grey')
                if result_submit_time:
                    print_info(f'Submit at {result_submit_time} (deadline is calculated relative to it)', color='grey')
            except PushFailedError:
                raise
        return True
    except RunFailedError:
        # print_info(e)
        return False


def grade_tasks(
        tasks: list[Task],
        tester: Tester,
        course_config: CourseConfig,
        public_course_driver: CourseDriver,
        private_course_driver: CourseDriver,
        user_id: int,
        send_time: datetime,
        inspect: bool = False
) -> bool:
    success = True
    for task in tasks:
        success &= grade_single_task(
            task,
            tester,
            course_config,
            public_course_driver,
            private_course_driver,
            user_id,
            send_time,
            inspect=inspect
        )
    return success


def _get_changes_using_real_folders(
        course_config: CourseConfig,
        current_folder: str,
        old_hash: str,
        current_repo_gitlab_path: str,
        gitlab_token: str,
) -> list[str]:
    gitlab_url_with_token = course_config.gitlab_url.replace('://', f'://gitlab-ci-token:{gitlab_token}@')

    with tempfile.TemporaryDirectory() as public_dir:
        with tempfile.TemporaryDirectory() as old_dir:
            # download public repo, minimal
            print_info(f'Cloning {course_config.public_repo} of {course_config.default_branch}...', color='white')
            # print_info('git clone:', color='grey')
            subprocess.run(
                f'git clone --depth=1 --branch={course_config.default_branch} '
                f'{course_config.gitlab_url}/{course_config.public_repo}.git {public_dir}',
                encoding='utf-8',
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
            )
            # print_info(r.stdout, color='grey')
            # print_info(f'ls -lah {public_dir}', color='grey')
            subprocess.run(
                f'ls -lah {public_dir}',
                encoding='utf-8',
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
            )
            # print_info(r.stdout, color='grey')

            # download old repo by hash, minimal
            print_info(f'Cloning {current_repo_gitlab_path} to get {old_hash}...', color='white')
            # print_info('git clone:', color='grey')
            subprocess.run(
                f'git clone --depth=1 --branch={course_config.default_branch} '
                f'{gitlab_url_with_token}/{current_repo_gitlab_path}.git {old_dir}',
                encoding='utf-8',
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
            )
            # print_info(r.stdout, color='grey')
            # print_info(f'git fetch origin {old_hash} && git checkout FETCH_HEAD:', color='grey')
            subprocess.run(
                f'git fetch origin {old_hash} && git checkout FETCH_HEAD',
                encoding='utf-8',
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                cwd=old_dir,
            )
            # print_info(r.stdout, color='grey')
            # print_info(f'ls -lah {old_dir}', color='grey')
            subprocess.run(
                f'ls -lah {old_dir}',
                encoding='utf-8',
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
            )
            # print_info(r.stdout, color='grey')

            # get diff
            print_info('Detected changes (filtering by public repo and git tracked files)', color='white')
            print_info('and filtering by git tracked files', color='white')
            changes = get_folders_diff_except_public(
                Path(public_dir),
                Path(old_dir),
                Path(current_folder),
                exclude_patterns=['.git'],
            )
            # filter by tracked by git
            git_tracked_files = get_tracked_files_list(Path(current_folder))
            changes = [f for f in changes if f in git_tracked_files]

            print_info('\nchanged_files:', color='white')
            for change in changes:
                print_info(f'  ->> {change}', color='white')

            return changes


def grade_on_ci(
        course_config: CourseConfig,
        course_schedule: CourseSchedule,
        public_course_driver: CourseDriver,
        private_course_driver: CourseDriver,
        tester: Tester,
        *,
        test_full_groups: bool = False,
) -> None:
    solution_root = os.environ['CI_PROJECT_DIR']

    current_time = datetime.now()
    commit_time = datetime.fromisoformat(os.environ['CI_COMMIT_TIMESTAMP'])
    # TODO: check datetime format
    pipeline_created_time: datetime | None = (
        datetime.strptime(os.environ['CI_PIPELINE_CREATED_AT'], '%Y-%m-%dT%H:%M:%SZ')
        if 'CI_PIPELINE_CREATED_AT' in os.environ else None
    )
    job_start_time: datetime | None = (
        datetime.strptime(os.environ['CI_JOB_STARTED_AT'], '%Y-%m-%dT%H:%M:%SZ')
        if 'CI_JOB_STARTED_AT' in os.environ else None
    )
    send_time = pipeline_created_time or current_time

    print_info(f'current_time {current_time}', color='grey')
    print_info(f'-> commit_time {commit_time}', color='grey')
    print_info(f'-> pipeline_created_time {pipeline_created_time}', color='grey')
    print_info(f'-> job_start_time {job_start_time}', color='grey')
    print_info(f'= using send_time {send_time}', color='grey')

    author_name = os.environ.get('CI_COMMIT_AUTHOR', None)
    current_commit_sha = os.environ.get('CI_COMMIT_SHA', None)
    prev_commit_sha = os.environ.get('CI_COMMIT_BEFORE_SHA', None)
    print_info(f'CI_COMMIT_AUTHOR {author_name}', color='grey')
    print_info(f'CI_COMMIT_SHA {current_commit_sha}', color='grey')
    print_info(f'CI_COMMIT_BEFORE_SHA {prev_commit_sha}', color='grey')

    gitlab_job_token = os.environ.get('CI_JOB_TOKEN') or ''

    print_info('Loading changes...', color='orange')
    # Get changes using real files difference
    try:
        current_repo_gitlab_path = os.environ['CI_PROJECT_PATH']
        changes = _get_changes_using_real_folders(
            course_config,
            current_folder=solution_root,
            old_hash=prev_commit_sha or course_config.default_branch,
            current_repo_gitlab_path=current_repo_gitlab_path,
            gitlab_token=gitlab_job_token,
        )
    except Exception as e:
        print_info('Ooops... Loading changes failed', color='red')
        print_info(e)

        print_info('Trying with git diff instead\n')
        # Get changed files via git
        try:
            changes = _get_git_changes(
                solution_root,
                course_config.gitlab_url + '/' + course_config.public_repo,
                author_name=author_name,
                current_commit_sha=current_commit_sha,
                prev_commit_sha=prev_commit_sha,
            )
        except GitException as e:
            print_info('Ooops... Loading changes failed', color='red')
            print_info(e)
            sys.exit(1)

    # Process Changed files to Changed tasks
    tasks: list[Task] = []
    groups: list[Group] = []
    for changed_file in changes:
        changed_task_dir = public_course_driver.get_task_dir_name(changed_file)
        if changed_task_dir is None or changed_task_dir not in course_schedule.tasks:
            continue

        # if changed_group_dir == '...':  # if task name is too long it's hidden
        #     changed_group_dir = course_schedule.tasks[changed_task_dir].group.name

        task = course_schedule.tasks[changed_task_dir]
        # group = course.groups[changed_group_dir]
        group = task.group

        # filter tasks and groups
        if group.is_started:
            if task not in tasks:
                tasks.append(task)
            if group not in groups:
                groups.append(group)

    # adding all tasks from group to testing
    if test_full_groups:
        print_info('Testing all tasks in changed groups...', color='orange')
        print_info(f'Changed groups: {[i.name for i in groups]}\n')

        tasks = []
        for group in groups:
            tasks.extend(group.tasks)
    else:
        print_info('Testing only changed tasks...', color='orange')
        print_info(f'Changed tasks: {[i.full_name for i in tasks]}\n')

    # Grade itself
    user_id = int(os.environ['GITLAB_USER_ID'])
    if tasks:
        success = grade_tasks(
            tasks,
            tester,
            course_config,
            public_course_driver,
            private_course_driver,
            user_id=user_id,
            send_time=send_time,
        )
    else:
        print_info('No changed tasks found :(', color='blue')
        print_info('Hint: commit some changes in tasks you are interested in')
        success = False

    if not success:
        sys.exit(1)
