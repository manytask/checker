"""Main executable file. Refer to cli module"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import click

from .actions.check import pre_release_check_tasks
from .actions.contributing import create_public_mr
from .actions.export import export_enabled, export_public_files
from .actions.grade import grade_on_ci
from .actions.grade_mr import grade_student_mrs, grade_students_mrs_to_master
from .course import CourseConfig, CourseSchedule, Task
from .course.driver import CourseDriver
from .testers import Tester
from .utils.glab import MASTER_BRANCH
from .utils.print import print_info

ClickTypeReadableFile = click.Path(exists=True, file_okay=True, readable=True, path_type=Path)
ClickTypeReadableDirectory = click.Path(exists=True, file_okay=False, readable=True, path_type=Path)
ClickTypeWritableDirectory = click.Path(file_okay=False, writable=True, path_type=Path)


@click.group()
@click.option('-c', '--config', envvar='CHECKER_CONFIG', type=ClickTypeReadableFile, default=None,
              help='Course config path')
@click.version_option(prog_name='checker')
@click.pass_context
def main(
        ctx: click.Context,
        config: Path | None,
) -> None:
    """Students' solutions Checker"""
    # Read course config and pass it to any command
    # If not provided - read .course.yml from the root
    config = config or Path() / '.course.yml'
    if not config.exists():
        config = Path() / 'tests' / '.course.yml'
    if not config.exists():
        config = Path() / 'tools' / '.course.yml'

    if not config.exists():
        raise FileNotFoundError('Unable to find `.course.yml` config')

    ctx.obj = CourseConfig.from_yaml(config)


@main.command()
@click.argument('root', required=False, type=ClickTypeReadableDirectory)
@click.option('--task', type=str, multiple=True, help='Task name to check')
@click.option('--group', type=str, multiple=True, help='Group name to check')
@click.option('--no-clean', is_flag=True, help='Clean or not check tmp folders')
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
@click.option('--parallelize', is_flag=True, help='Execute parallel checking of tasks')
@click.option('--contributing', is_flag=True, help='Run task check for students` contribution (decrease verbosity)')
@click.pass_context
def check(
        ctx: click.Context,
        root: Path | None = None,
        task: list[str] | None = None,
        group: list[str] | None = None,
        no_clean: bool = False,
        dry_run: bool = False,
        parallelize: bool = False,
        contributing: bool = False,
) -> None:
    """Run task pre-release checking"""
    course_config: CourseConfig = ctx.obj

    root = root or Path()  # Run in some dir or in current dir
    # TODO: swatch to relative to the root
    root = Path(__file__).parent.parent.parent
    course_driver = CourseDriver(
        root_dir=root,
        layout=course_config.layout,
        reference_source=True,
    )
    course_schedule = CourseSchedule(
        deadlines_config=course_driver.get_deadlines_file_path(),
    )
    tester = Tester.create(
        system=course_config.system,
        cleanup=not no_clean,
        dry_run=dry_run,
    )

    tasks: list[Task] | None = None
    if group:
        tasks = []
        for group_name in group:
            if group_name in course_schedule.groups:
                tasks.extend(course_schedule.groups[group_name].tasks)
            else:
                print_info(f'Provided wrong group name: {group_name}', color='red')
                sys.exit(1)
    elif task:
        tasks = []
        for task_name in task:
            if task_name in course_schedule.tasks:
                tasks.append(course_schedule.tasks[task_name])
            else:
                print_info(f'Provided wrong task name: {task_name}', color='red')
                sys.exit(1)

    pre_release_check_tasks(
        course_schedule,
        course_driver,
        tester,
        tasks=tasks,
        parallelize=parallelize, contributing=contributing
    )


@main.command()
@click.argument('reference_root', required=False, type=ClickTypeReadableDirectory)
@click.option('--test-full-groups', is_flag=True, help='Test all tasks in changed groups')
@click.pass_context
def grade(
        ctx: click.Context,
        reference_root: Path | None = None,
        test_full_groups: bool = False,
) -> None:
    """Run task grading"""
    course_config: CourseConfig = ctx.obj

    reference_root = reference_root or Path()
    # TODO: swatch to relative to the root
    reference_root = Path(__file__).parent.parent.parent
    course_driver = CourseDriver(
        root_dir=Path(os.environ['CI_PROJECT_DIR']),
        reference_root_dir=reference_root,
        layout=course_config.layout,
        reference_tests=True,
    )
    course_schedule = CourseSchedule(
        deadlines_config=course_driver.get_deadlines_file_path(),
    )
    tester = Tester.create(
        system=course_config.system,
    )

    grade_on_ci(
        course_config,
        course_schedule,
        course_driver,
        tester,
        test_full_groups=test_full_groups
    )
    # TODO: think inspect


@main.command()
@click.argument('reference_root', required=False, type=ClickTypeReadableDirectory)
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
@click.pass_context
def grade_mrs(
        ctx: click.Context,
        reference_root: Path | None = None,
        dry_run: bool = False,
) -> None:
    """Run task grading student's MRs (current user)"""
    course_config: CourseConfig = ctx.obj

    reference_root = reference_root or Path()
    # TODO: swatch to relative to the root
    reference_root = Path(__file__).parent.parent.parent
    course_driver = CourseDriver(
        root_dir=Path(os.environ['CI_PROJECT_DIR']),
        reference_root_dir=reference_root,
        layout=course_config.layout,
        reference_tests=True,
    )
    course_schedule = CourseSchedule(
        deadlines_config=course_driver.get_deadlines_file_path(),
    )

    grade_student_mrs(
        course_config,
        course_schedule,
        course_driver,
        dry_run=dry_run,
    )
    # TODO: think inspect


@main.command()
@click.argument('root', required=False, type=ClickTypeReadableDirectory)
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
@click.pass_context
def grade_students_mrs(
        ctx: click.Context,
        root: Path | None = None,
        dry_run: bool = False,
) -> None:
    """Check all mrs is correct"""
    course_config: CourseConfig = ctx.obj

    root = root or Path()
    # TODO: swatch to relative to the root
    root = Path(__file__).parent.parent.parent
    course_driver = CourseDriver(
        root_dir=root,
        layout=course_config.layout,
    )
    course_schedule = CourseSchedule(
        deadlines_config=course_driver.get_deadlines_file_path(),
    )

    grade_students_mrs_to_master(course_config, course_schedule, course_driver, dry_run=dry_run)


@main.command()
@click.argument('root', required=False, type=ClickTypeReadableDirectory)
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
@click.pass_context
def old_export(
        ctx: click.Context,
        root: Path | None = None,
        dry_run: bool = False,
) -> None:
    """Export enabled tasks and stuff to public repository"""
    course_config: CourseConfig = ctx.obj

    root = root or Path()
    # TODO: swatch to relative to the root
    root = Path(__file__).parent.parent.parent
    course_driver = CourseDriver(
        root_dir=root,
        layout=course_config.layout,
    )
    course_schedule = CourseSchedule(
        deadlines_config=course_driver.get_deadlines_file_path(),
    )

    export_enabled(course_config, course_schedule, course_driver, dry_run=dry_run)


@main.command()
@click.argument('root', required=False, type=ClickTypeReadableDirectory)
@click.option('--export-dir', type=ClickTypeWritableDirectory, help='TEMP dir to export into')
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
@click.option('--no-cleanup', is_flag=True, help='Do not cleanup export dir')
@click.pass_context
def export_public(
        ctx: click.Context,
        root: Path | None = None,
        export_dir: Path | None = None,
        dry_run: bool = False,
        no_cleanup: bool = False,
) -> None:
    """Export enabled tasks and stuff to public repository"""
    course_config: CourseConfig = ctx.obj

    root = root or Path()
    # TODO: swatch to relative to the root
    root = Path(__file__).parent.parent.parent
    course_driver = CourseDriver(
        root_dir=root,
        layout=course_config.layout,
    )
    course_schedule = CourseSchedule(
        deadlines_config=course_driver.get_deadlines_file_path(),
    )

    export_dir = export_dir or Path(tempfile.mkdtemp())
    if not export_dir.exists():
        export_dir.mkdir(exist_ok=True, parents=True)

    export_public_files(export_dir, course_config, course_schedule, course_driver, dry_run=dry_run)

    if not no_cleanup:
        shutil.rmtree(export_dir)


@main.command()
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
@click.pass_context
def create_contributing_mr(
        ctx: click.Context,
        dry_run: bool = False,
) -> None:
    """Move public project to private as MR"""
    course_config: CourseConfig = ctx.obj

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
        print_info('merge_commit_sha = None. Skip it.', color='orange')
        return

    mr_state = object_attributes['state']
    target_branch = object_attributes['target_branch']

    if mr_state != 'merged':
        print_info(f'mr_state = {mr_state}. Skip it.', color='orange')
        return

    if target_branch != MASTER_BRANCH:
        print_info(f'target_branch = {target_branch}. Skip it.', color='orange')
        return

    create_public_mr(course_config, object_attributes, dry_run=dry_run)


if __name__ == '__main__':  # pragma: nocover
    main()
