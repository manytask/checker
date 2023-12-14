from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from checker.course import Course, FileSystemTask
from checker.tester import Tester
from checker.utils import print_info

from .configs import CheckerConfig, DeadlinesConfig
from .exceptions import BadConfig, TestingError


ClickReadableFile = click.Path(
    exists=True, file_okay=True, readable=True, path_type=Path
)
ClickReadableDirectory = click.Path(
    exists=True, file_okay=False, readable=True, path_type=Path
)
ClickWritableDirectory = click.Path(file_okay=False, writable=True, path_type=Path)


@click.group(context_settings={"show_default": True})
@click.option(
    "--checker-config",
    type=ClickReadableFile,
    default=".checker.yml",
    help="Path to the checker config file.",
)
@click.option(
    "--deadlines-config",
    type=ClickReadableFile,
    default=".deadlines.yml",
    help="Path to the deadlines config file.",
)
@click.version_option(package_name="manytask-checker")
@click.pass_context
def cli(
    ctx: click.Context,
    checker_config: Path,
    deadlines_config: Path,
) -> None:
    """Manytask checker - automated tests for students' assignments."""
    ctx.ensure_object(dict)
    ctx.obj = {
        "course_config_path": checker_config,
        "deadlines_config_path": deadlines_config,
    }


@cli.command()
@click.argument("root", type=ClickReadableDirectory, default=".")
@click.option(
    "-v/-s", "--verbose/--silent", is_flag=True, default=True, help="Verbose output"
)
@click.pass_context
def validate(
    ctx: click.Context,
    root: Path,
    verbose: bool,
) -> None:
    """
    Validate the configuration files, plugins and tasks.
    1. Validate the configuration files content.
    2. Validate mentioned plugins.
    3. Check all tasks are valid and consistent with the deadlines.
    """

    print_info("Validating configuration files...")
    try:
        checker_config = CheckerConfig.from_yaml(ctx.obj["course_config_path"])
        deadlines_config = DeadlinesConfig.from_yaml(ctx.obj["deadlines_config_path"])
    except BadConfig as e:
        print_info("Configuration Failed", color="red")
        print_info(e)
        exit(1)
    print_info("Ok", color="green")

    print_info("Validating Course Structure (and tasks configs)...")
    try:
        course = Course(checker_config, deadlines_config, root)
        course.validate()
    except BadConfig as e:
        print_info("Course Validation Failed", color="red")
        print_info(e)
        exit(1)
    print_info("Ok", color="green")

    print_info("Validating tester...")
    try:
        tester = Tester(course, checker_config, verbose=verbose)
        tester.validate()
    except BadConfig as e:
        print_info("Tester Validation Failed", color="red")
        print_info(e)
        exit(1)
    print_info("Ok", color="green")


@cli.command()
@click.argument("root", type=ClickReadableDirectory, default=".")
@click.argument("reference_root", type=ClickReadableDirectory, default=".")
@click.option(
    "-t",
    "--task",
    type=str,
    multiple=True,
    default=None,
    help="Task name to check (multiple possible)",
)
@click.option(
    "-g",
    "--group",
    type=str,
    multiple=True,
    default=None,
    help="Group name to check (multiple possible)",
)
@click.option(
    "-p",
    "--parallelize",
    is_flag=True,
    default=True,
    help="Execute parallel checking of tasks",
)
@click.option(
    "-n",
    "--num-processes",
    type=int,
    default=os.cpu_count(),
    help="Num of processes parallel checking",
)
@click.option("--no-clean", is_flag=True, help="Clean or not check tmp folders")
@click.option(
    "-v/-s",
    "--verbose/--silent",
    is_flag=True,
    default=True,
    help="Verbose tests output",
)
@click.option(
    "--dry-run", is_flag=True, help="Do not execute anything, only log actions"
)
@click.pass_context
def check(
    ctx: click.Context,
    root: Path,
    reference_root: Path,
    task: list[str] | None,
    group: list[str] | None,
    parallelize: bool,
    num_processes: int,
    no_clean: bool,
    verbose: bool,
    dry_run: bool,
) -> None:
    """Check private repository: run tests, lint etc. First forces validation."""
    # validate first
    ctx.invoke(validate, root=root, verbose=verbose)  # TODO: check verbose level

    # load configs
    checker_config = CheckerConfig.from_yaml(ctx.obj["course_config_path"])
    deadlines_config = DeadlinesConfig.from_yaml(ctx.obj["deadlines_config_path"])

    # read filesystem, check existing tasks
    course = Course(checker_config, deadlines_config, root, username="private")

    # validate tasks and groups if passed
    filesystem_tasks: dict[str, FileSystemTask] = dict()
    if task:
        for filesystem_task in course.get_tasks(enabled=True):
            if filesystem_task.name in task:
                filesystem_tasks[filesystem_task.name] = filesystem_task
    if group:
        for filesystem_group in course.get_groups(enabled=True):
            if filesystem_group.name in group:
                for filesystem_task in filesystem_group.tasks:
                    filesystem_tasks[filesystem_task.name] = filesystem_task
    if filesystem_tasks:
        print_info(f"Checking tasks: {', '.join(filesystem_tasks.keys())}")

    # create tester to... to test =)
    tester = Tester(
        course, checker_config, verbose=verbose, cleanup=not no_clean, dry_run=dry_run
    )

    # run tests
    # TODO: progressbar on parallelize
    try:
        tester.run(
            tasks=list(filesystem_tasks.values()) if filesystem_tasks else None,
            report=False,
        )
    except TestingError as e:
        print_info("TESTING FAILED", color="red")
        print_info(e)
        exit(1)
    except Exception as e:
        print_info("UNEXPECTED ERROR", color="red")
        print_info(e)
        exit(1)
    print_info("TESTING PASSED", color="green")


@cli.command()
@click.argument("root", type=ClickReadableDirectory, default=".")
@click.argument("reference_root", type=ClickReadableDirectory, default=".")
@click.option(
    "--submit-score", is_flag=True, help="Submit score to the Manytask server"
)
@click.option(
    "--timestamp", type=str, default=None, help="Timestamp to use for the submission"
)
@click.option(
    "--username", type=str, default=None, help="Username to use for the submission"
)
@click.option("--no-clean", is_flag=True, help="Clean or not check tmp folders")
@click.option(
    "-v/-s",
    "--verbose/--silent",
    is_flag=True,
    default=False,
    help="Verbose tests output",
)
@click.option(
    "--dry-run", is_flag=True, help="Do not execute anything, only log actions"
)
@click.pass_context
def grade(
    ctx: click.Context,
    root: Path,
    reference_root: Path,
    submit_score: bool,
    timestamp: str | None,
    username: str | None,
    no_clean: bool,
    verbose: bool,
    dry_run: bool,
) -> None:
    """
    Process the configuration file and grade the tasks.
    """
    # load configs
    checker_config = CheckerConfig.from_yaml(ctx.obj["course_config_path"])
    deadlines_config = DeadlinesConfig.from_yaml(ctx.obj["deadlines_config_path"])

    # read filesystem, check existing tasks
    course = Course(
        checker_config, deadlines_config, root, reference_root, username=username
    )

    # detect changes to test
    filesystem_tasks: list[FileSystemTask] = list()
    # TODO: detect changes
    filesystem_tasks = [
        task for task in course.get_tasks(enabled=True) if task.name == "hello_world"
    ]

    # create tester to... to test =)
    tester = Tester(
        course, checker_config, verbose=verbose, cleanup=not no_clean, dry_run=dry_run
    )

    # run tests
    # TODO: progressbar on parallelize
    try:
        tester.run(tasks=filesystem_tasks, report=True)
    except TestingError as e:
        print_info("TESTING FAILED", color="red")
        print_info(e)
        exit(1)
    except Exception as e:
        print_info("UNEXPECTED ERROR", color="red")
        print_info(e)
        exit(1)
    print_info("TESTING PASSED", color="green")


if __name__ == "__main__":
    cli()
