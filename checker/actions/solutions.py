from typing import Union, Any, Generator
from datetime import datetime, timedelta
import ast
import io
import json
import random
import os
import time
import tokenize
import typing as tp
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
import gitlab

from ..course import Course, Task
from ..utils.print import print_info
from ..utils.files import file_match_patterns
from ..utils.repos import GITLAB, MASTER_BRANCH, get_private_project, get_students_projects, get_student_file_link


SCORE_API_URL = 'https://py.manytask.org/api/score'

END_TIMEDELTA = timedelta(days=8)  # Export only tasks ended in some period
NO_ENDED_TIMEDELTA = timedelta(days=2)  # Export only tasks will end in some period
EXPORT_IGNORE_FILE_PATTERNS = []  # ['__init__.py']
EXPORT_FILE_EXTENSIONS = ['.py', '.cfg', '.yml', '.yaml']
SIMILARITY_MIN_THRESHOLD = 0.5

PARALLEL_WORKERS = 8


def _get_ended_solutions(course: Course) -> Generator[tuple[Task, list[str]], None, None]:
    now_ = datetime.now()  # TODO: check timezone
    # TODO: read env for group names
    group_names = os.environ.get('GROUP_NAMES', None)
    if group_names:
        print_info(f'Looking for {group_names}...')
        group_names = group_names.split(',')
        ended_tasks = []
        for group_name in group_names:
            if group_name in course.groups:
                group = course.groups[group_name]
                ended_tasks.extend(group.tasks)
            else:
                print_info(f'Can not find group {group_name}', color='orange')
                continue
        print_info([task.full_name for task in ended_tasks])
    else:
        print_info('Looking for ended tasks...')
        now_ = datetime.now()  # TODO: check timezone
        ended_tasks = course.get_tasks(enabled=True)
        ended_tasks = [task for task in ended_tasks if task.group.second_deadline > now_ - END_TIMEDELTA]
        ended_tasks = [task for task in ended_tasks if now_ - NO_ENDED_TIMEDELTA < task.group.second_deadline < now_ + END_TIMEDELTA]

        print_info(f'Export enabled tasks ended in <{END_TIMEDELTA}> or will end in <{NO_ENDED_TIMEDELTA}> period: ')
        print_info([task.full_name for task in ended_tasks])

    for task in ended_tasks:
        print_info(f'Processing task "{task.full_name}"...', color='pink')

        relative_task_paths = {
            *[i.relative_to(task.private_dir) for i in task.private_dir.glob('**/*') if i.is_file() and i.suffix in EXPORT_FILE_EXTENSIONS],
            *[i.relative_to(task.public_dir) for i in task.public_dir.glob('**/*') if i.is_file() and i.suffix in EXPORT_FILE_EXTENSIONS],
        }
        task_files = [
            str(i) for i in relative_task_paths
            if not file_match_patterns(i, [*EXPORT_IGNORE_FILE_PATTERNS, *task.config.test_files])
        ]

        print_info('Filter files', [*EXPORT_IGNORE_FILE_PATTERNS, *task.config.test_files], color='grey')
        print_info('Found files', task_files, color='grey')

        yield task, task_files


def download_solutions(
        course: Course,
        dry_run: bool = False,
        solutions_dir: Union[str, Path] = 'exported_solutions',
        parallelize: bool = False
) -> None:
    assert not dry_run, 'Only true execution are supported'
    assert parallelize, 'Only parallel execution are supported'

    # Get gitlab projects
    private_project = get_private_project()
    students_projects = get_students_projects()

    report: dict[str, Any] = {
        'total_files': 0,
        'tasks': {},
    }
    for task, task_files in _get_ended_solutions(course):
        task_solution_dir = solutions_dir / task.group.name
        task_solution_dir.mkdir(parents=True, exist_ok=True)

        report['tasks'].update({
            f'{task.full_name}/{filename}': {
                'solutions': 0,
                'unique_solutions': 0,
                'time': 0,
            } for filename in task_files
        })
        report['total_files'] += len(task_files)

        task_start_time = time.time()
        for filename in task_files:
            start_time = time.time()
            print_info(f"Start processing file: {filename}", color='grey')
            remote_path = task.group.name + '/' + task.name + '/' + filename
            local_path = task_solution_dir / f'{task.name}__{filename.replace("/", "__")}'

            print_info(f"downloading solved solutions...", color='grey')
            _, _, students_codes = get_all_students_code(private_project, students_projects, task.name, remote_path, solved=True)

            print_info(f"writing unique solutions...", color='grey')
            print_info(f"students_codes {len(students_codes)}", color='grey')
            total_solutions_count, unique_solutions_count = write_unique_solutions(students_codes, remote_path, local_path)

            report['tasks'][f'{task.full_name}/{filename}']['unique_solutions'] = unique_solutions_count
            report['tasks'][f'{task.full_name}/{filename}']['solutions'] = total_solutions_count
            report['tasks'][f'{task.full_name}/{filename}']['time'] = time.time() - start_time

            print_info(f"Done in {time.time() - start_time:.2f}s", color='grey')
        print_info(f"Done in {time.time() - task_start_time:.2f}s")

    print_info(json.dumps(report, indent=4))


# --------------------------------


def get_file_data(private_project_id: int, student_project_id: int, student_project_name, task_name: str, path_to_file: str, solved: bool = True) -> tp.Optional[str]:
    try:
        full_private_project = GITLAB.projects.get(private_project_id)
        full_student_project = GITLAB.projects.get(student_project_id)

        if solved:
            project_users_filtered_by_name = full_student_project.users.list(search=full_student_project.name)
            project_users_filtered_by_name = [u.id for u in project_users_filtered_by_name]
            if len(project_users_filtered_by_name) == 0:
                # print_info(f'No users in project {full_student_project.name}:{student_project_id} with name {full_student_project.name}', color='red')
                return None
            if len(project_users_filtered_by_name) != 1:
                print_info(f'Multiple users in filter {full_student_project.name}: {project_users_filtered_by_name}', color='orange')
                project_users_filtered_by_name = project_users_filtered_by_name[:1]

            user_id = project_users_filtered_by_name[0]

            score = _get_score(task_name, user_id)
            if score is None:
                return None
            # print(score, 'for', task_name, user_id, full_student_project.name)

        student_file = full_student_project.files.get(path_to_file, ref=MASTER_BRANCH).decode()
        try:
            solution_template_file = full_private_project.files.get(path_to_file, ref=MASTER_BRANCH).decode()
        except gitlab.exceptions.GitlabGetError:
            solution_template_file = None
        try:
            canonical_file = full_private_project.files.get('tests/' + path_to_file, ref=MASTER_BRANCH).decode()
        except gitlab.exceptions.GitlabGetError:
            canonical_file = None

        if student_file == solution_template_file:
            # logging.debug('File is equal to template. Skipping: %s', get_student_file_link(student_project_name, path_to_file))
            return None
        elif student_file == canonical_file:
            print_info('File is equal to canonical solution: ', get_student_file_link(student_project_name, path_to_file))
            return student_file
        else:
            # print_info('Found good file ', get_student_file_link(student_project_name, path_to_file), color='grey')
            return student_file

    except gitlab.exceptions.GitlabGetError as e:
        # print_info('  File not found: ', get_student_file_link(student_project_name, path_to_file))
        # print_info(e)
        pass

    return None


def remove_comments_and_docstrings(source: str) -> str:
    # https://stackoverflow.com/a/62074206/14208137
    # TODO: rewrite

    out = ""
    prev_toktype = tokenize.INDENT
    last_lineno = -1
    last_col = 0
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        token_type = tok[0]
        token_string = tok[1]
        start_line, start_col = tok[2]
        end_line, end_col = tok[3]
        ltext = tok[4]
        if start_line > last_lineno:
            last_col = 0
        if start_col > last_col:
            out += (" " * (start_col - last_col))
        if token_type == tokenize.COMMENT:
            pass
        elif token_type == tokenize.STRING:
            if prev_toktype != tokenize.INDENT and prev_toktype != tokenize.NEWLINE and start_col > 0:
                out += token_string
        else:
            out += token_string
        prev_toktype = token_type
        last_col = end_col
        last_lineno = end_line

    return '\n'.join(i for i in out.splitlines() if i.strip())


def get_all_students_code(private_project, students_projects, task_name, path_to_file, solved: bool = True) -> tuple[bytes, bytes, dict[str, bytes]]:
    path = Path(path_to_file)

    students_codes: dict[str, bytes] = {}

    # Get unique solutions
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        random.shuffle(students_projects)
        future_to_author = {
            executor.submit(get_file_data, private_project.id, project.id, project.name, task_name, path.as_posix(), solved=solved): project.name
            for project in students_projects
        }

        for future in as_completed(future_to_author):
            student_repo_name = future_to_author[future]

            try:
                data = future.result()
            except Exception as e:
                data = None
                print_info(f'Error getting {student_repo_name} files with exception {e}', color='orange')

            # print_info(f'    {student_repo_name=} {"None" if data is None else len(data)}', color='grey')

            if data is None:
                continue

            students_codes[student_repo_name] = data

    full_private_project = GITLAB.projects.get(private_project.id)

    try:
        template_code = full_private_project.files.get(path_to_file, ref=MASTER_BRANCH).decode()
    except gitlab.exceptions.GitlabGetError:
        print_info(f"Failed to load template code for: {path_to_file}", color='red')
        template_code = None
    try:
        canonical_code = full_private_project.files.get('tests/' + path_to_file, ref=MASTER_BRANCH).decode()
    except gitlab.exceptions.GitlabGetError:
        print_info(f"Failed to load canonical code for: {path_to_file}", color='red')
        canonical_code = None

    return template_code, canonical_code, students_codes


def write_unique_solutions(students_codes: dict[str, bytes], remote_path, local_path) -> tuple[int, int]:
    path = Path(remote_path)
    unique_solutions_code: dict[int, list[bytes]] = {}
    unique_solutions_authors: dict[int, list[str]] = {}

    # Get unique solutions
    total_solutions_count = 0
    for student_repo_name, data in students_codes.items():
        total_solutions_count += 1

        data_cleaned = data.decode('utf8')
        try:
            data_cleaned = remove_comments_and_docstrings(data_cleaned)
            dump = ast.dump(ast.parse(data_cleaned))
        except SyntaxError:
            continue
        except Exception:
            dump = data_cleaned

        dump_hash = hash(dump)
        if dump_hash not in unique_solutions_code:
            unique_solutions_authors[dump_hash] = []
            unique_solutions_code[dump_hash] = []

        unique_solutions_authors[dump_hash].append(student_repo_name)
        if data not in unique_solutions_code[dump_hash]:
            unique_solutions_code[dump_hash].append(data)

    # Write to local file
    if not isinstance(local_path, Path):
        local_path = Path(local_path)
    local_path.parent.mkdir(exist_ok=True, parents=True)
    print_info(f'{len(unique_solutions_code)} unique_solutions_code into {local_path}', color='grey')
    with local_path.open('w') as file_:
        for dump_hash, codes in unique_solutions_code.items():
            print(
                '',
                '',
                '#' * 120,
                f'# total identical solutions: {len(unique_solutions_authors[dump_hash]) - len(codes) + 1} \t' +
                f'# total "similar" solutions: {len(unique_solutions_authors[dump_hash])}',
                *[f'# {author[:20]:<{20}} \t{get_student_file_link(author, path)}' for author in
                  unique_solutions_authors[dump_hash]],
                '#' * 60,
                file=file_, sep='\n', end='\n'
            )
            for code in codes:
                file_.write(code.decode('utf8'))
                print(
                    '',
                    '#' * 60,
                    file=file_, sep='\n', end='\n'
                )

    return total_solutions_count, len(unique_solutions_code)


def _get_score(task_name: str, user_id: int) -> None:
    # Do not expose token in logs.
    tester_token = os.environ['TESTER_TOKEN']  # TODO: use other token

    data = {
        'token': tester_token,
        'task': task_name,
        'user_id': user_id,
    }
    response = None
    for _ in range(3):
        response = requests.get(url=SCORE_API_URL, data=data)

        if response.status_code < 500:
            break
        time.sleep(1.0)

    if response.status_code >= 500:
        pass
        # response.raise_for_status()
        # print_info(f'{response.status_code}: {response.text}', color='orange')
    # Client error often means early submission
    elif response.status_code >= 400:
        pass
        # print_info(f'{response.status_code}: {response.text}', color='orange')
    else:
        try:
            result = response.json()
            return result['score']
        except (json.JSONDecodeError, KeyError):
            pass

    return None
