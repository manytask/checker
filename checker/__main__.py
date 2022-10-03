"""Main executable file. Refer to cli module"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import click

from .actions.check import pre_release_check_tasks

# from .actions.contributing import create_public_mr  # type: ignore
from .actions.export import export_public_files
from .actions.grade import grade_on_ci
from .actions.grade_mr import grade_student_mrs, grade_students_mrs_to_master
from .course import CourseConfig, CourseSchedule, Task
from .course.driver import CourseDriver
from .testers import Tester
from .utils.glab import GitlabConnection
from .utils.print import print_info

ClickTypeReadableFile = click.Path(exists=True, file_okay=True, readable=True, path_type=Path)
ClickTypeReadableDirectory = click.Path(exists=True, file_okay=False, readable=True, path_type=Path)
ClickTypeWritableDirectory = click.Path(file_okay=False, writable=True, path_type=Path)


@click.group()
@click.option('-c', '--config', envvar='CHECKER_CONFIG', type=ClickTypeReadableFile, default=None,
              help='Course config path')
@click.version_option(package_name='manytask-checker')
@click.pass_context
def main(
        ctx: click.Context,
        config: Path | None,
) -> None:
    """Students' solutions *checker*"""
    # Read course config and pass it to any command
    # If not provided - read .course.yml from the root
    config = config or Path() / '.course.yml'
    if not config.exists():
        config = Path() / 'tests' / '.course.yml'
    if not config.exists():
        config = Path() / 'tools' / '.course.yml'

    if not config.exists():
        raise FileNotFoundError('Unable to find `.course.yml` config')

    execution_folder = Path()

    ctx.obj = {
        'course_config': CourseConfig.from_yaml(config),
        'execution_folder': execution_folder,
    }


@main.command()
@click.argument('root', required=False, type=ClickTypeReadableDirectory)
@click.option('--task', type=str, multiple=True, help='Task name to check')
@click.option('--group', type=str, multiple=True, help='Group name to check')
@click.option('--no-clean', is_flag=True, help='Clean or not check tmp folders')
@click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
@click.option('--parallelize', is_flag=True, help='Execute parallel checking of tasks')
@click.option('--num-processes', type=int, default=None, help='Num of processes parallel checking (default: unlimited)')
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
        num_processes: int | None = None,
        contributing: bool = False,
) -> None:
    """Run task pre-release checking"""
    context: dict[str, Any] = ctx.obj
    course_config: CourseConfig = context['course_config']
    execution_folder: Path = context['execution_folder']

    root = root or execution_folder
    course_driver = CourseDriver(
        root_dir=root,
        reference_root_dir=root,
        layout=course_config.layout,
        use_reference_source=True,
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
        parallelize=parallelize,
        num_processes=num_processes,
        contributing=contributing,
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
    """Run student's tasks (current ci user)"""
    context: dict[str, Any] = ctx.obj
    course_config: CourseConfig = context['course_config']
    execution_folder: Path = context['execution_folder']

    reference_root = reference_root or execution_folder
    course_driver = CourseDriver(
        root_dir=Path(os.environ['CI_PROJECT_DIR']),
        reference_root_dir=reference_root,
        layout=course_config.layout,
        use_reference_tests=True,
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
        test_full_groups=test_full_groups,
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
    """Run student's MRs grading (current git user)"""
    context: dict[str, Any] = ctx.obj
    course_config: CourseConfig = context['course_config']
    execution_folder: Path = context['execution_folder']

    reference_root = reference_root or execution_folder
    course_driver = CourseDriver(
        root_dir=Path(os.environ['CI_PROJECT_DIR']),
        reference_root_dir=reference_root,
        layout=course_config.layout,
        use_reference_tests=True,
    )
    course_schedule = CourseSchedule(
        deadlines_config=course_driver.get_deadlines_file_path(),
    )

    username = os.environ['CI_PROJECT_NAME']

    gitlab_connection = GitlabConnection(
        gitlab_host_url=course_config.gitlab_url,
        job_token=os.environ.get('CI_JOB_TOKEN'),
    )

    grade_student_mrs(
        course_config,
        course_schedule,
        course_driver,
        gitlab_connection,
        username,
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
    """Run students' MRs grading (all users)"""
    context: dict[str, Any] = ctx.obj
    course_config: CourseConfig = context['course_config']
    execution_folder: Path = context['execution_folder']

    root = root or execution_folder
    course_driver = CourseDriver(
        root_dir=root,
        reference_root_dir=root,
        layout=course_config.layout,
    )
    course_schedule = CourseSchedule(
        deadlines_config=course_driver.get_deadlines_file_path(),
    )

    gitlab_connection = GitlabConnection(
        gitlab_host_url=course_config.gitlab_url,
        private_token=course_config.gitlab_service_token,
    )

    grade_students_mrs_to_master(
        course_config,
        course_schedule,
        course_driver,
        gitlab_connection,
        dry_run=dry_run,
    )


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
    """Export enabled tasks to public repo"""
    context: dict[str, Any] = ctx.obj
    course_config: CourseConfig = context['course_config']
    execution_folder: Path = context['execution_folder']

    root = root or execution_folder
    course_driver = CourseDriver(
        root_dir=root,
        reference_root_dir=root,
        layout=course_config.layout,
    )
    course_schedule = CourseSchedule(
        deadlines_config=course_driver.get_deadlines_file_path(),
    )

    export_dir = export_dir or Path(tempfile.mkdtemp())
    if not export_dir.exists():
        export_dir.mkdir(exist_ok=True, parents=True)

    export_public_files(
        course_config,
        course_schedule,
        course_driver,
        export_dir,
        dry_run=dry_run,
    )

    if not no_cleanup:
        shutil.rmtree(export_dir)
        print_info(f'No cleanup flag. Exported files stored in {export_dir}')


# @main.command()
# @click.option('--dry-run', is_flag=True, help='Do not execute anything, only print')
# @click.pass_context
def create_contributing_mr(
        ctx: click.Context,
        dry_run: bool = False,
) -> None:
    """Move public project to private as MR"""
    context: dict[str, Any] = ctx.obj
    course_config: CourseConfig = context['course_config']
    # execution_folder: Path = context['execution_folder']

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

    if target_branch != course_config.default_branch:
        print_info(f'target_branch = {target_branch}. Skip it.', color='orange')
        return

    # create_public_mr(course_config, object_attributes, dry_run=dry_run)


if __name__ == '__main__':  # pragma: nocover
    main()
