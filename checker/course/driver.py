"""
Classes to map course schedule to real filesystem
"""
from __future__ import annotations

from pathlib import Path
from warnings import warn

from .schedule import Task, Group


class CourseDriver:
    """The interlayer between course and file system
    Course can have different layouts; Now implemented: @see self.LAYOUTS

    * flat [deprecated]
        - .gitlab-ci.yml
        - .gitignore
        - README.md
        - task_1/
        - ...
        - tests/
            - .course.yml
            - .deadlines.yml
            - task_1/
            - ...

    * groups
        - .gitlab-ci.yml
        - .gitignore
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
            - .course.yml
            - .deadlines.yml
            - group_1/
                - task_1/
                - ...

    * lectures
        - .gitlab-ci.yml
        - .gitignore
        - .course.yml
        - .deadlines.yml
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
        self.root_dir = root_dir
        self.reference_root_dir = reference_root_dir or root_dir
        self.reference_source = reference_source
        self.reference_tests = reference_tests

        assert layout in CourseDriver.LAYOUTS, f'Course layout <{layout}> are not implemented'
        if layout == 'flat':
            warn(f'<{layout}> layout is deprecated', DeprecationWarning)
        self.layout = layout

    def get_deadlines_file_path(self) -> Path:
        if self.layout == 'groups':
            deadlines_file_path = self.reference_root_dir / 'tests' / '.deadlines.yml'
        elif self.layout == 'flat':
            deadlines_file_path = self.reference_root_dir / 'tests' / '.deadlines.yml'
        else:
            assert False, 'Not Reachable'

        assert deadlines_file_path.exists()
        return deadlines_file_path

    def get_config_file_path(self) -> Path:
        if self.layout == 'groups':
            config_file_path = self.root_dir / 'tests' / '.course.yml'
        elif self.layout == 'flat':
            config_file_path = self.root_dir / 'tests' / '.course.yml'
        else:
            assert False, 'Not Reachable'

        assert config_file_path.exists()
        return config_file_path

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
                task_source_dir = self.reference_root_dir / 'tests' / task.group.name / task.name
            else:
                task_source_dir = self.root_dir / task.group.name / task.name
        elif self.layout == 'flat':
            if self.reference_source:
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
                public_tests_dir = self.reference_root_dir / '.' / task.group.name / task.name
                private_tests_dir = self.reference_root_dir / 'tests' / task.group.name / task.name
            else:
                public_tests_dir = self.root_dir / '.' / task.group.name / task.name
                private_tests_dir = self.root_dir / 'tests' / task.group.name / task.name
        elif self.layout == 'flat':
            if self.reference_tests:
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
