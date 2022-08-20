"""
Classes to map course schedule to real filesystem
"""
from __future__ import annotations

from pathlib import Path
from warnings import warn

from ..exceptions import BadConfig
from .schedule import Group, Task


class CourseDriver:
    """The interlayer between course and file system
    Course can have different layouts; Now implemented: @see self.LAYOUTS

    * flat [deprecated]
        - .gitignore
        - .gitlab-ci.yml
        - .releaser-ci.yml
        - README.md
        - task_1/
        - ...
        - tests/
            - .course.yml
            - .deadlines.yml
            - task_1/
            - ...

    * groups
        - .course.yml
        - .deadlines.yml
        - .gitignore
        - .gitlab-ci.yml
        - .releaser-ci.yml
        - README.md
        - group_1/
            - task_1/
            - ...
        - ...
        - lectures/
            - group_1/
            - ...
        - solutions/
            - group_1/
            - ...
        - tests/
            - group_1/
                - task_1/
                - ...

    * lectures
        - .course.yml
        - .deadlines.yml
        - .gitignore
        - .gitlab-ci.yml
        - .releaser-ci.yml
        - README.md
        - group_1/
            tasks:
                - task_1/
                - ...
            tests/
                - task_1/
                - ...
            lecture/
                - ...
            solutions/
                - ...
        - ...

    * tasks (tba)
        - .gitlab-ci.yml
        - .gitignore
        - .course.yml
        - .deadlines.yml
        - README.md
        - group_1/
            - task_1/
                - template/
                - tests/
                - solution/
            - ...
    """

    LAYOUTS = ['flat', 'groups']

    def __init__(
            self,
            root_dir: Path,
            reference_root_dir: Path | None = None,
            layout: str = 'groups',
            reference_source: bool = False,
            reference_tests: bool = False,
    ):
        """
        @param root_dir: Root folder of the repo to test
        @param reference_root_dir: Root folder of private repo if necessary
        @param layout: @see available LAYOUTS in class docstring
        @param reference_source: Use source from private repo (reference_root_dir)
        @param reference_tests: Use tests from private repo (reference_root_dir)
        """

        self.root_dir = root_dir
        self.reference_root_dir: Path | None = reference_root_dir
        self.reference_source = reference_source
        self.reference_tests = reference_tests

        if self.reference_source or self.reference_tests:
            assert self.reference_root_dir, 'To use reference roots `reference_root_dir` should be provided'

        assert layout in CourseDriver.LAYOUTS, f'Course layout <{layout}> are not implemented'
        if layout == 'flat':
            warn(f'<{layout}> layout is deprecated', DeprecationWarning)
        self.layout = layout

    def get_deadlines_file_path(
            self,
    ) -> Path:
        deadlines_file_path: Path
        if self.layout == 'groups':
            if self.reference_root_dir:
                deadlines_file_path = self.reference_root_dir / '.deadlines.yml'
            else:
                raise BadConfig('Unable to find deadlines file without `reference_root_dir`')
        elif self.layout == 'flat':
            if self.reference_root_dir:
                deadlines_file_path = self.reference_root_dir / 'tests' / '.deadlines.yml'
            else:
                raise BadConfig('Unable to find deadlines file without `reference_root_dir`')
        else:
            assert False, 'Not Reachable'

        if not deadlines_file_path or not deadlines_file_path.exists():
            raise BadConfig(f'Deadlines file <{deadlines_file_path}> not exists')

        return deadlines_file_path

    def get_group_lecture_dir(
            self,
            group: Group
    ) -> Path | None:
        lecture_dir: Path | None = None
        if self.layout == 'groups':
            lecture_dir = self.root_dir / 'lectures' / group.name
        elif self.layout == 'flat':
            lecture_dir = None
        else:
            assert False, 'Not Reachable'

        lecture_dir = lecture_dir if lecture_dir and lecture_dir.exists() else None
        return lecture_dir

    def get_group_solution_dir(
            self,
            group: Group,
    ) -> Path | None:
        solution_dir: Path | None = None
        if self.layout == 'groups':
            solution_dir = self.root_dir / 'solutions' / group.name
        elif self.layout == 'flat':
            solution_dir = None
        else:
            assert False, 'Not Reachable'

        solution_dir = solution_dir if solution_dir and solution_dir.exists() else None
        return solution_dir

    def get_group_source_dir(
            self,
            group: Group,
    ) -> Path | None:
        source_dir: Path | None = None
        if self.layout == 'groups':
            source_dir = self.root_dir / group.name
        elif self.layout == 'flat':
            source_dir = None
        else:
            assert False, 'Not Reachable'

        source_dir = source_dir if source_dir and source_dir.exists() else None
        return source_dir

    def get_task_source_dir(
            self,
            task: Task,
    ) -> Path | None:
        task_source_dir: Path | None = None
        if self.layout == 'groups':
            if self.reference_source:
                assert self.reference_root_dir
                task_source_dir = self.reference_root_dir / 'tests' / task.group.name / task.name
            else:
                task_source_dir = self.root_dir / task.group.name / task.name
        elif self.layout == 'flat':
            if self.reference_source:
                assert self.reference_root_dir
                task_source_dir = self.reference_root_dir / 'tests' / task.name
            else:
                task_source_dir = self.root_dir / task.name
        else:
            assert False, 'Not Reachable'

        task_source_dir = task_source_dir if task_source_dir and task_source_dir.exists() else None
        return task_source_dir

    def get_task_test_dirs(
            self,
            task: Task,
    ) -> tuple[Path | None, Path | None]:
        public_tests_dir: Path | None = None
        private_tests_dir: Path | None = None
        if self.layout == 'groups':
            if self.reference_tests:
                assert self.reference_root_dir
                public_tests_dir = self.reference_root_dir / '.' / task.group.name / task.name
                private_tests_dir = self.reference_root_dir / 'tests' / task.group.name / task.name
            else:
                public_tests_dir = self.root_dir / '.' / task.group.name / task.name
                private_tests_dir = self.root_dir / 'tests' / task.group.name / task.name
        elif self.layout == 'flat':
            if self.reference_tests:
                assert self.reference_root_dir
                public_tests_dir = self.reference_root_dir / '.' / task.name
                private_tests_dir = self.reference_root_dir / 'tests' / task.name
            else:
                public_tests_dir = self.root_dir / '.' / task.name
                private_tests_dir = self.root_dir / 'tests' / task.name
        else:
            assert False, 'Not Reachable'

        public_tests_dir = public_tests_dir if public_tests_dir and public_tests_dir.exists() else None
        private_tests_dir = private_tests_dir if private_tests_dir and private_tests_dir.exists() else None
        return public_tests_dir, private_tests_dir
