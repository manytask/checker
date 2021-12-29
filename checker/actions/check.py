from __future__ import annotations

import io
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stdout, redirect_stderr

from ..course import Course, Task
from ..system.tester import Tester, ChecksFailedError
from ..utils.print import print_info, print_task_info


def check_single_task(tester: Tester, task: Task, verbose: bool = False, catch_output: bool = False) -> str | None:
    if catch_output:
        f = io.StringIO()
        with redirect_stderr(f), redirect_stdout(f):
            print_task_info(task.full_name)
            try:
                tester.run_tests(task, task.private_dir, verbose=verbose, normalize_output=True)
            except ChecksFailedError as e:
                out = f.getvalue()
                raise ChecksFailedError(e.msg, out + e.output) from e
            else:
                out = f.getvalue()
                return out
    else:
        print_task_info(task.full_name)
        tester.run_tests(task, task.private_dir, verbose=verbose)


def check_tasks(tester: Tester, tasks: list[Task], parallelize: bool = False, verbose: bool = True) -> bool:
    # Check itself
    if parallelize:
        num_cores = multiprocessing.cpu_count()
        print_info(f'Parallelize task checks with <{num_cores}> cores...', color='blue')

        success = True
        # with ThreadPoolExecutor(max_workers=num_cores) as e:
        with ProcessPoolExecutor(max_workers=num_cores) as e:
            check_futures = {
                e.submit(check_single_task, tester, task, verbose=verbose, catch_output=True)
                for task in tasks
            }

            for future in as_completed(check_futures):
                try:
                    captured_out = future.result()
                except ChecksFailedError as e:
                    print_info(e.output)
                    success &= False
                except Exception as e:
                    print_info('Unknown exception:', e, color='red')
                    raise e
                else:
                    print_info(captured_out)
        return success
    else:
        for task in tasks:
            check_single_task(tester, task, verbose=verbose, catch_output=False)

        return True


def pre_release_check_tasks(
        course: Course,
        tasks: list[Task] | None = None,
        cleanup: bool = True, dry_run: bool = False,
        parallelize: bool = False, contributing: bool = False,
) -> None:
    # Filter tasks
    if not tasks:
        if contributing:
            tasks = course.get_tasks(started=True)
            print_info('Testing started groups...', color='yellow')
            print_info([i.name for i in course.get_groups(started=True)])
        else:
            tasks = course.get_tasks(enabled=True)
            print_info('Testing enabled groups...', color='yellow')
            print_info([i.name for i in course.get_groups(enabled=True)])
    else:
        print_info('Testing specifying tasks...', color='yellow')
        print_info([i.full_name for i in tasks])

    # Create tester.. to test
    tester = Tester(cleanup=cleanup, dry_run=dry_run)

    success = check_tasks(tester, tasks, parallelize=parallelize, verbose=not contributing)
    # if not success:
    #     raise ChecksFailedError('Got one or more errors during the testing')
    if not success:
        sys.exit(1)


