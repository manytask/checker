from __future__ import annotations

import io
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout

from ..course import CourseDriver, CourseSchedule, Task
from ..exceptions import RunFailedError
from ..testers import Tester
from ..utils.print import print_info, print_task_info


def _check_single_task(
        task: Task,
        tester: Tester,
        course_driver: CourseDriver,
        verbose: bool = False,
        catch_output: bool = False,
) -> str | None:
    source_dir = course_driver.get_task_source_dir(task)
    public_tests_dir, private_tests_dir = course_driver.get_task_test_dirs(task)
    assert source_dir, f'{source_dir=} have to exists'
    assert public_tests_dir, f'{public_tests_dir=} have to exists'
    assert private_tests_dir, f'{private_tests_dir=} have to exists'

    if catch_output:
        f = io.StringIO()
        with redirect_stderr(f), redirect_stdout(f):
            print_task_info(task.full_name)
            try:
                tester.test_task(
                    source_dir, public_tests_dir, private_tests_dir,
                    verbose=verbose, normalize_output=True
                )
            except RunFailedError as e:
                out = f.getvalue()
                raise RunFailedError(e.msg, out + (e.output or '')) from e
            else:
                out = f.getvalue()
                return out
    else:
        print_task_info(task.full_name)
        tester.test_task(
            source_dir, public_tests_dir, private_tests_dir,
            verbose=verbose, normalize_output=True
        )
        return None


def _check_tasks(
        tasks: list[Task],
        tester: Tester,
        course_driver: CourseDriver,
        parallelize: bool = False,
        num_processes: int | None = None,
        verbose: bool = True,
) -> bool:
    # Check itself
    if parallelize:
        _num_processes = num_processes or multiprocessing.cpu_count()
        print_info(f'Parallelize task checks with <{_num_processes}> processes...', color='blue')

        success = True
        # with ThreadPoolExecutor(max_workers=num_cores) as e:
        with ProcessPoolExecutor(max_workers=_num_processes) as e:
            check_futures = {
                e.submit(_check_single_task, task, tester, course_driver, verbose=verbose, catch_output=True)
                for task in tasks
            }

            for future in as_completed(check_futures):
                try:
                    captured_out = future.result()
                except RunFailedError as e:
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
            try:
                _check_single_task(task, tester, course_driver, verbose=verbose, catch_output=False)
            except RunFailedError:
                return False
            except Exception as e:
                print_info('Unknown exception:', e, color='red')
                raise e

        return True


def pre_release_check_tasks(
        course_schedule: CourseSchedule,
        course_driver: CourseDriver,
        tester: Tester,
        tasks: list[Task] | None = None,
        *,
        parallelize: bool = False,
        num_processes: int | None = None,
        contributing: bool = False,
) -> None:
    # select tasks or use `tasks` param
    if tasks:
        print_info('Testing specifying tasks...', color='yellow')
        print_info([i.full_name for i in tasks])
    else:
        if contributing:
            tasks = course_schedule.get_tasks(started=True)
            print_info('Testing started groups...', color='yellow')
            print_info([i.name for i in course_schedule.get_groups(started=True)])
        else:
            tasks = course_schedule.get_tasks(enabled=True)
            print_info('Testing enabled groups...', color='yellow')
            print_info([i.name for i in course_schedule.get_groups(enabled=True)])

    # tests itself
    success = _check_tasks(
        tasks,
        tester,
        course_driver,
        parallelize=parallelize,
        num_processes=num_processes,
        verbose=not contributing,
    )

    if not success:
        sys.exit(1)
