"""Main executable file. Refer to cli module"""
from __future__ import annotations

from pathlib import Path
import sys
import json
import os
import io
from contextlib import redirect_stdout, redirect_stderr

import click

from .utils.print import print_info
from .utils.repos import MASTER_BRANCH
from .course import Course, Task, PUBLIC_DIR
from .actions.check import pre_release_check_tasks
from .actions.export import export_enabled
from .actions.grade import grade_on_ci
from .actions.grade_mr import grade_students_mrs_to_master
from .actions.lectures import render_lectures
from .actions.solutions import download_solutions
from .actions.contributing import create_public_mr


@click.group()
@click.version_option(prog_name='checker')
def cli() -> None:
    """Python course cli checker"""
    pass


@cli.command()
@click.option('--task', type=str, multiple=True, help='Task name to check')
@click.option('--group', type=str, multiple=True, help='Group name to check')
@click.option('--no-clean', is_flag=True, help='Clean or not check tmp folders')
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
@click.option('--parallelize', is_flag=True, help='Execute parallel checking of tasks')
@click.option('--contributing', is_flag=True, help='Run task check for students` contribution (decrease verbosity)')
def check(
        task: list[str] | None = None,
        group: list[str] | None = None,
        no_clean: bool = False,
        dry_run: bool = False,
        parallelize: bool = False,
        contributing: bool = False
) -> None:
    """Run task pre-release checking"""
    course = Course(skip_missed_sources=contributing)

    tasks: list[Task] | None = None
    if group:
        tasks = []
        for group_name in group:
            if group_name in course.groups:
                tasks.extend(course.groups[group_name].tasks)
            else:
                print_info(f'Provided wrong group name: {group_name}', color='red')
                sys.exit(1)
    elif task:
        tasks = []
        for task_name in task:
            if task_name in course.tasks:
                tasks.append(course.tasks[task_name])
            else:
                print_info(f'Provided wrong task name: {task_name}', color='red')
                sys.exit(1)

    pre_release_check_tasks(
        course, tasks=tasks,
        cleanup=not no_clean, dry_run=dry_run,
        parallelize=parallelize, contributing=contributing
    )


@cli.command()
# @click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
@click.option('--inspect', is_flag=False, flag_value=Path('report.txt'), type=click.Path(exists=False, file_okay=True, writable=True, path_type=Path), default=None, help='Full print to inspect in file. Use carefully!')
@click.option('--test-full-groups', is_flag=True, help='Test all tasks in changed groups')
def grade(
        # dry_run: bool = False,
        inspect: Path | None = None,
        test_full_groups: bool = False,
) -> None:
    """Run task grading"""

    try:
        course = Course(source_dir=Path(os.environ['CI_PROJECT_DIR']), skip_missed_sources=True)
    except ValueError as e:
        print_info('Can not find some tasks or tests. Try to update repo from upstream.', color='red')
        sys.exit(1)

    if inspect is None:
        grade_on_ci(course, dry_run=False, test_full_groups=test_full_groups)
    else:
        if inspect.exists():
            raise ValueError(f'File {inspect} exists!')
        inspect.touch(0o666)

        f = io.StringIO()
        with redirect_stderr(f), redirect_stdout(f):
            out = '[ERROR]'
            try:
                grade_on_ci(course, dry_run=False, inspect=inspect is not None, test_full_groups=test_full_groups)
            except Exception as e:
                out = f.getvalue()
                if hasattr(e, 'output'):
                    out += e.output
            else:
                out = f.getvalue()

        with open(inspect, 'w') as report_f:
            report_f.write(out)


@cli.command()
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
def grade_students_mrs(
        dry_run: bool = False,
) -> None:
    """Check all mrs is correct"""

    course = Course()

    grade_students_mrs_to_master(course, dry_run=False)


@cli.command()
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
def export(
        dry_run: bool = False,
) -> None:
    """Export enabled tasks and stuff to public repository"""
    course = Course()

    export_enabled(course, dry_run=dry_run)


@cli.command()
@click.option('--build-dir', type=click.Path(exists=False, file_okay=False, writable=True, path_type=Path), default=PUBLIC_DIR / 'lecture_build', help='Build output folder')
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
def lectures(
        build_dir: Path = PUBLIC_DIR / 'lecture_build',
        dry_run: bool = False,
) -> None:
    """Render enabled lectures"""
    build_dir.mkdir(exist_ok=True)

    course = Course()

    render_lectures(course, dry_run=dry_run, build_dir=build_dir)


@cli.command()
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
@click.option('--solutions-dir', type=click.Path(exists=False, file_okay=False, writable=True, path_type=Path), default=PUBLIC_DIR / 'exported_solutions', help='Solutions output folder')
@click.option('--parallelize', is_flag=True, help='Execute parallel checking of tasks')
def solutions(
        dry_run: bool = False,
        solutions_dir: Path = PUBLIC_DIR / 'exported_solutions',
        parallelize: bool = False,
) -> None:
    """Render enabled lectures"""
    solutions_dir.mkdir(exist_ok=True)

    course = Course()

    download_solutions(course, dry_run=dry_run, solutions_dir=solutions_dir, parallelize=parallelize)


@cli.command()
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
@click.option('--plagiarism-dir', type=click.Path(exists=False, file_okay=False, writable=True, path_type=Path), default=PUBLIC_DIR / 'plagiarism_solutions', help='Plagiarism output folder')
@click.option('--parallelize', is_flag=True, help='Execute parallel checking of tasks')
def plagiarism(
        dry_run: bool = False,
        plagiarism_dir: Path = PUBLIC_DIR / 'plagiarism_solutions',
        parallelize: bool = False,
) -> None:
    """Render enabled lectures"""
    raise NotImplementedError

    plagiarism_dir.mkdir(exist_ok=True)

    course = Course()

    # check_plagiarism_solutions(course, dry_run=dry_run, plagiarism_dir=plagiarism_dir, parallelize=parallelize)


@cli.command()
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
def create_contributing_mr(
        dry_run: bool = False,
) -> None:
    """Move public project to private as MR"""
    trigger_payload = os.environ.get('TRIGGER_PAYLOAD', 'None')
    print_info('trigger_payload', trigger_payload)

    # trigger_payload_dict = json.loads(trigger_payload)
    with open(trigger_payload, 'r') as json_file:
        trigger_payload_dict = json.load(json_file)

    event_type = trigger_payload_dict['event_type']

    if event_type != 'merge_request':
        print_info(f'event_type = {event_type}. Skip it.', color='orange')
        return

    object_attributes = trigger_payload_dict['object_attributes']
    merge_commit_sha = object_attributes['merge_commit_sha']

    if merge_commit_sha is None:
        print_info(f'merge_commit_sha = None. Skip it.', color='orange')
        return

    mr_state = object_attributes['state']
    target_branch = object_attributes['target_branch']

    if mr_state != 'merged':
        print_info(f'mr_state = {mr_state}. Skip it.', color='orange')
        return

    if target_branch != MASTER_BRANCH:
        print_info(f'target_branch = {target_branch}. Skip it.', color='orange')
        return

    create_public_mr(object_attributes, dry_run=dry_run)


if __name__ == '__main__':  # pragma: nocover
    cli()
