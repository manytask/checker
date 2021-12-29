import json
import os
import subprocess
import sys
import time
from datetime import datetime

import requests

from .utils import print_info, print_task_info
from .course import Course, Group, Task
from .tester import Tester, ChecksFailedError, BuildFailedError


REPORT_API_URL = 'https://py.manytask.org/api/report'


class GitException(Exception):
    pass


def _get_git_changes(solution_root: str, git_changes_type: str = 'log_between_no_upstream') -> list[str]:
    """
    :param solution_root: Full path to solutions folder
    :param git_changes_type: one of
        'diff_last', 'diff_between', 'log_between_no_merges', 'log_between_by_author', 'log_between_no_upstream'
    """
    author_name = os.environ.get('CI_COMMIT_AUTHOR', None)
    if author_name is None and git_changes_type == 'log_between_by_author':
        git_changes_type = 'log_between_no_merges'

    current_commit_sha = os.environ.get('CI_COMMIT_SHA', None)
    prev_commit_sha = os.environ.get('CI_COMMIT_BEFORE_SHA', None)
    if set(prev_commit_sha) == {'0'}:  # first commit or merge request
        prev_commit_sha = None

    if git_changes_type == 'diff_between' and (current_commit_sha is None or prev_commit_sha is None):
        print_info(f'CI_COMMIT_SHA or CI_COMMIT_BEFORE_SHA is wrong pipeline_diff can not be used. Using std `git show`')
        print_info(f'CI_COMMIT_SHA: {current_commit_sha}, CI_COMMIT_BEFORE_SHA: {prev_commit_sha}!')
        git_changes_type = 'diff_last'

    print_info('Loading changes...', color='orange')

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
                f'while read commit_hash; do git show --oneline --name-only $commit_hash | tail -n+2; done | sort | uniq',
                encoding='utf-8',
                stdout=subprocess.PIPE,
                shell=True
            ).stdout
            print_info(git_status)
            changes = git_status.split('\n')
        elif git_changes_type == 'log_between_by_author':
            print_info(f'Looking log between {prev_commit_sha} and {current_commit_sha} by author="{author_name.split(" ")[0]}"...')
            prev_commit_sha = '' if prev_commit_sha is None else prev_commit_sha
            git_status = subprocess.run(
                f'cd {solution_root} && '
                f'git log --pretty="%H" --author="{author_name.split(" ")[0]}" {prev_commit_sha or ""}..{current_commit_sha} | '
                f'while read commit_hash; do git show --oneline --name-only $commit_hash | tail -n+2; done | sort | uniq',
                encoding='utf-8',
                stdout=subprocess.PIPE,
                shell=True
            ).stdout
            print_info(git_status)
            changes = git_status.split('\n')
        elif git_changes_type == 'log_between_no_upstream':
            current_public_repo = 'public-2021-fall.git'
            print_info(f'Looking log_between_no_upstream between {prev_commit_sha} and {current_commit_sha} which not in `{current_public_repo}`...')

            result = subprocess.run(
                f'cd {solution_root} && '
                f'(git remote rm upstream | true) &&'
                f'git remote add upstream https://gitlab.manytask.org/py-tasks/{current_public_repo} &&'
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
                f'git log --pretty="%H" {prev_commit_sha or ""}..{current_commit_sha} --no-merges --not --remotes=upstream | '
                f'while read commit_hash; do git show --oneline --name-only $commit_hash | tail -n+2; done | sort | uniq',
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


def _push_report(task_name: str, user_id: int, score: float, commit_time: datetime = None, check_deadline: bool = True) -> None:
    # Do not expose token in logs.
    tester_token = os.environ['TESTER_TOKEN']

    data = {
        'token': tester_token,
        'task': task_name,
        'user_id': user_id,
        'score': score,
        'check_deadline': check_deadline,
    }
    if commit_time:
        data['commit_time'] = commit_time
    response = None
    for _ in range(3):
        response = requests.post(url=REPORT_API_URL, data=data)

        if response.status_code < 500:
            break
        time.sleep(1.0)

    if response.status_code >= 500:
        response.raise_for_status()
    # Client error often means early submission
    elif response.status_code >= 400:
        raise Exception(f'{response.status_code}: {response.text}')
    else:
        try:
            result = response.json()
            print_info(
                f'Final score for @{result["username"]} (according to deadlines): {result["score"]}',
                color='blue'
            )
        except (json.JSONDecodeError, KeyError):
            pass


def grade_single_task(tester: Tester, task: Task, user_id: int, commit_time: datetime, inspect: bool = False) -> bool:
    print_task_info(task.full_name)
    try:
        score = tester.run_tests(task, task.source_dir, verbose=inspect, normalize_output=inspect)
        print_info(f'\nSolution score: {score}', color='green')
        if task.config.review:
            print_info(f'\nThis task is "review-able", so, open MR and wait till review.', color='blue')
        elif not inspect:
            _push_report(task.name, user_id, score, commit_time)
        return True
    except (BuildFailedError, ChecksFailedError):
        # print_info(e)
        return False


def grade_tasks(tester: Tester, tasks: list[Task], user_id: int, commit_time: datetime, inspect: bool = False) -> bool:
    success = True
    for task in tasks:
        success &= grade_single_task(tester, task, user_id, commit_time, inspect=inspect)
    return success


def grade_on_ci(course: Course, dry_run: bool = False, inspect: bool = False, test_full_groups: bool = False):
    solution_root = os.environ['CI_PROJECT_DIR']

    commit_time = datetime.fromisoformat(os.environ['CI_COMMIT_TIMESTAMP'])
    current_time = datetime.now()

    print_info(f'commit_time {commit_time}', color='grey')
    print_info(f'current_time {current_time}', color='grey')

    # Get changed files via git
    try:
        changes = _get_git_changes(solution_root)
    except GitException as e:
        print_info('Ooops... Loading changes failed', color='red')
        print_info(e)
        sys.exit(1)

    # Process Changed files to Changed tasks
    tasks: list[Task] = []
    groups: list[Group] = []
    for changed_file in changes:
        changed_file = changed_file.split(os.path.sep, maxsplit=2)

        if len(changed_file) < 2:  # Changed file not in subdir
            continue

        changed_group_dir, changed_task_dir = changed_file[0:2]

        if changed_task_dir not in course.tasks:
            continue

        if changed_group_dir == '...':  # if task name is too long it's hidden
            changed_group_dir = course.tasks[changed_task_dir].group.name

        task = course.tasks[changed_task_dir]
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
        print_info(f'Testing only changed tasks...', color='orange')
        print_info(f'Changed tasks: {[i.full_name for i in tasks]}\n')

    # Create tester.. to test
    tester = Tester(cleanup=True, dry_run=dry_run)

    # Grade itself
    user_id = int(os.environ['GITLAB_USER_ID'])
    if tasks:
        success = grade_tasks(tester, tasks, user_id=user_id, commit_time=commit_time, inspect=inspect)
    else:
        print_info('No changed tasks found :(', color='blue')
        print_info('Hint: commit some changes in tasks you are interested in')
        success = False

    if not success and not inspect:
        sys.exit(1)
