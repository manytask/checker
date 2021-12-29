from typing import Union, Any
import json
import time
from pathlib import Path

from .course import Course
from .utils import print_info
from .repos import get_private_project, get_students_projects


def check_plagiarism_solutions(course: Course, dry_run: bool = False,
                               plagiarism_dir: Union[str, Path] = 'plagiarism_solutions',
                               parallelize: bool = False) -> None:
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
        task_solution_dir = plagiarism_dir / task.group.name
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
            local_path = task_solution_dir / f'{task.name}__{filename}'

            print_info(f"downloading...", color='grey')
            template_code, canonical_code, students_codes = get_all_students_code(private_project, students_projects, task.name, remote_path)

            print_info(f"measuring similarity...", color='grey')
            similarity = get_code_similarity(students_codes)
            similarity = np.array(similarity)
            similarity = np.where(similarity < SIMILARITY_MIN_THRESHOLD, 0, similarity)

            print_info(f"communities generation...", color='grey')
            G = nx.from_numpy_matrix(similarity)
            comp = nx.algorithms.community.girvan_newman(G)
            k = 8
            for communities in itertools.islice(comp, k):
                pl = [c for c in communities if 1 < len(c)]  # < 5]
                print(pl)

            # comp = nx.algorithms.community.asyn_lpa_communities(G)
            # print([c for c in comp if len(c) > 1])

            # report['tasks'][f'{task.full_name}/{filename}']['unique_solutions'] = unique_solutions_count
            # report['tasks'][f'{task.full_name}/{filename}']['solutions'] = total_solutions_count
            report['tasks'][f'{task.full_name}/{filename}']['time'] = time.time() - start_time

            print_info(f"Done in {time.time() - start_time:.2f}s", color='grey')
        print_info(f"Done in {time.time() - task_start_time:.2f}s")

    print_info(json.dumps(report, indent=4))


def get_code_similarity(students_codes: dict[str, bytes]) -> list[list[float]]:
    similarity = [[0. for _ in students_codes] for _ in students_codes]

    codes = [code for _, code in students_codes.items()]

    for i, (ref_username, ref_code) in enumerate(students_codes.items()):
        result = pycode_similar.detect([ref_code, *codes], keep_prints=False, module_level=False)

        for j in range(len(result)):
            sum_plagiarism_percent, sum_plagiarism_count, sum_total_count = pycode_similar.summarize(result[j][1])
            similarity[i][j] = sum_plagiarism_percent

    return similarity
