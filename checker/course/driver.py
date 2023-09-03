"""
Classes to map course schedule to real filesystem
"""
from __future__ import annotations

import os
from pathlib import Path
from warnings import warn

from ..exceptions import BadConfig
from .schedule import Group, Task


class CourseDriver:
    """The interlayer between course and file system
    Course can have different layouts;
    You can select 2 layouts: for private and for public repo
    for script to know how to read private script and how to write to the public repo
    Now implemented: @see self.PUBLIC_LAYOUTS, self.PRIVATE_LAYOUTS

    * flat [deprecated] (public & private)
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

    * groups (public & private)
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

    * lectures (private)
        - .course.yml
        - .deadlines.yml
        - .gitignore
        - .gitlab-ci.yml
        - .releaser-ci.yml
        - README.md
        - group_1/
            lecture/ [optional]
            review/ [optional]
            tasks/
                - task_1/
                    - private/ [optional]
                        - test_private.py
                    - public/ [optional]
                        - test_public.py
                    - template/ [optional]
                        - solution.py
                    - solution/
                        - solution.py
                    - README.md
                    - .tester.json [optional]
                - ...
        - ...
    * lectures (private)
        - ...
        - group_1/
            ...
            tasks/
                - task_1/
                    - test_public.py
                    - solution.py
                    - README.md
                    - .tester.json [optional]
                - ...
        - ...

    For templates:
        * search - will search template in public folder
        * create - will search gold solution in private folder and create template from it
        * create_or_search - will search template in public folder or will create template from gold solution
    """

    LAYOUTS = ['flat', 'groups', 'lectures']
    TEMPLATES = ['create', 'search', 'create_or_search']
    REPO_TYPES = ['public', 'private']

    def __init__(
            self,
            root_dir: Path,
            repo_type: str = 'public',
            layout: str = 'groups',
            template: str = 'search',
    ):
        """
        @param root_dir: Root folder of the repo to be a driver on
        @param repo_type: Type of repository public (students repos / public) or private (main private repo)
        @param layout: @see available LAYOUTS in class docstring
        @param template: @see available TEMPLATES in class var and utils -> clear_gold_solution function
        """

        assert root_dir.exists(), f'Root dir <{root_dir}> not exists'
        self.root_dir = root_dir

        assert repo_type in CourseDriver.REPO_TYPES, f'Repo type <{repo_type}> not in private, public'
        self.repo_type = repo_type

        assert layout in CourseDriver.LAYOUTS, f'Course layout <{layout}> are not implemented'
        if layout == 'flat':
            warn(f'<{layout}> layout is deprecated', DeprecationWarning)
        self.layout = layout

        assert template in CourseDriver.TEMPLATES, f'Template <{layout}> are not implemented'
        self.template = template

    def get_deadlines_file_path(
            self,
            raise_if_not_exists: bool = True,
    ) -> Path:
        if self.repo_type == 'public':
            raise BadConfig('Unable to find `deadlines` file in public repo')

        deadlines_file_path: Path
        if self.layout == 'lectures':
            deadlines_file_path = self.root_dir / '.deadlines.yml'
        elif self.layout == 'groups':
            deadlines_file_path = self.root_dir / '.deadlines.yml'
        elif self.layout == 'flat':
            deadlines_file_path = self.root_dir / 'tests' / '.deadlines.yml'
        else:
            assert False, 'Not Reachable'  # pragma: no cover

        if raise_if_not_exists and (not deadlines_file_path or not deadlines_file_path.exists()):
            raise BadConfig(f'Deadlines file <{deadlines_file_path}> not exists')

        return deadlines_file_path

    def get_group_lecture_dir(
            self,
            group: Group,
            check_exists: bool = True,
    ) -> Path | None:
        lecture_dir: Path | None = None

        if self.layout == 'lectures':
            lecture_dir = self.root_dir / group.name / 'lecture'
        elif self.layout == 'groups':
            lecture_dir = self.root_dir / 'lectures' / group.name
        elif self.layout == 'flat':
            lecture_dir = None
        else:
            assert False, 'Not Reachable'  # pragma: no cover

        if check_exists:
            lecture_dir = lecture_dir if lecture_dir and lecture_dir.exists() else None

        return lecture_dir

    def get_group_submissions_review_dir(
            self,
            group: Group,
            check_exists: bool = True,
    ) -> Path | None:
        review_dir: Path | None = None

        if self.layout == 'lectures':
            # both public and private
            review_dir = self.root_dir / group.name / 'review'
        elif self.layout == 'groups':
            # both public and private
            review_dir = self.root_dir / 'solutions' / group.name
        elif self.layout == 'flat':
            review_dir = None
        else:
            assert False, 'Not Reachable'  # pragma: no cover

        if check_exists:
            review_dir = review_dir if review_dir and review_dir.exists() else None

        return review_dir

    def get_group_dir(
            self,
            group: Group,
            check_exists: bool = True,
    ) -> Path | None:
        group_root_dir: Path | None = None

        if self.layout == 'lectures':
            group_root_dir = self.root_dir / group.name
        elif self.layout == 'groups':
            group_root_dir = self.root_dir / group.name
        elif self.layout == 'flat':
            group_root_dir = None
        else:
            assert False, 'Not Reachable'  # pragma: no cover

        if check_exists:
            group_root_dir = group_root_dir if group_root_dir and group_root_dir.exists() else None

        return group_root_dir

    def get_task_dir(
            self,
            task: Task,
            check_exists: bool = True,
    ) -> Path | None:
        task_root_dir: Path | None = None

        if self.layout == 'lectures':
            task_root_dir = self.root_dir / task.group.name / 'tasks' / task.name
        elif self.layout == 'groups':
            task_root_dir = self.root_dir / task.group.name / task.name
        elif self.layout == 'flat':
            task_root_dir = self.root_dir / task.name
        else:
            assert False, 'Not Reachable'  # pragma: no cover

        if check_exists:
            task_root_dir = task_root_dir if task_root_dir and task_root_dir.exists() else None

        return task_root_dir

    def get_task_solution_dir(
            self,
            task: Task,
            check_exists: bool = True,
    ) -> Path | None:
        task_solution_dir: Path | None = None

        if self.layout == 'lectures':
            if self.repo_type == 'private':
                task_solution_dir = self.root_dir / task.group.name / 'tasks' / task.name / 'solution'
            else:
                task_solution_dir = self.root_dir / task.group.name / 'tasks' / task.name
        elif self.layout == 'groups':
            if self.repo_type == 'private':
                task_solution_dir = self.root_dir / 'tests' / task.group.name / task.name
            else:
                task_solution_dir = self.root_dir / task.group.name / task.name
        elif self.layout == 'flat':
            if self.repo_type == 'private':
                task_solution_dir = self.root_dir / 'tests' / task.name
            else:
                task_solution_dir = self.root_dir / task.name
        else:
            assert False, 'Not Reachable'  # pragma: no cover

        if check_exists:
            task_solution_dir = task_solution_dir if task_solution_dir and task_solution_dir.exists() else None

        return task_solution_dir

    def get_task_template_dir(
            self,
            task: Task,
            check_exists: bool = True,
    ) -> Path | None:
        task_template_dir: Path | None = None

        if self.layout == 'lectures':
            if self.repo_type == 'private':
                task_template_dir = self.root_dir / task.group.name / 'tasks' / task.name / 'template'
            else:
                task_template_dir = self.root_dir / task.group.name / 'tasks' / task.name
        elif self.layout == 'groups':
            # both public and private
            task_template_dir = self.root_dir / task.group.name / task.name
        elif self.layout == 'flat':
            # both public and private
            task_template_dir = self.root_dir / task.name
        else:
            assert False, 'Not Reachable'  # pragma: no cover

        if check_exists:
            task_template_dir = task_template_dir if task_template_dir and task_template_dir.exists() else None

        return task_template_dir

    def get_task_public_test_dir(
            self,
            task: Task,
            check_exists: bool = True,
    ) -> Path | None:
        public_tests_dir: Path | None = None

        if self.layout == 'lectures':
            if self.repo_type == 'private':
                public_tests_dir = self.root_dir / task.group.name / 'tasks' / task.name / 'public'
            else:
                public_tests_dir = self.root_dir / task.group.name / 'tasks' / task.name
        elif self.layout == 'groups':
            # both public and private
            public_tests_dir = self.root_dir / task.group.name / task.name
        elif self.layout == 'flat':
            # both public and private
            public_tests_dir = self.root_dir / task.name
        else:
            assert False, 'Not Reachable'  # pragma: no cover

        if check_exists:
            public_tests_dir = public_tests_dir if public_tests_dir and public_tests_dir.exists() else None

        return public_tests_dir

    def get_task_private_test_dir(
            self,
            task: Task,
            check_exists: bool = True,
    ) -> Path | None:
        private_tests_dir: Path | None = None

        if self.layout == 'lectures':
            if self.repo_type == 'private':
                private_tests_dir = self.root_dir / task.group.name / 'tasks' / task.name / 'private'
            else:
                private_tests_dir = None
        elif self.layout == 'groups':
            if self.repo_type == 'private':
                private_tests_dir = self.root_dir / 'tests' / task.group.name / task.name
            else:
                private_tests_dir = None
        elif self.layout == 'flat':
            if self.repo_type == 'private':
                private_tests_dir = self.root_dir / 'tests' / task.name
            else:
                private_tests_dir = None
        else:
            assert False, 'Not Reachable'  # pragma: no cover

        if check_exists:
            private_tests_dir = private_tests_dir if private_tests_dir and private_tests_dir.exists() else None

        return private_tests_dir

    def get_task_dir_name(
            self,
            path: str,
    ) -> str | None:
        path_split = path.split(os.path.sep, maxsplit=2)
        if len(path_split) < 2:  # Changed file not in subdir
            return None
        if self.layout == 'lectures':
            return path_split[1]
        elif self.layout == 'groups':
            return path_split[1]
        elif self.layout == 'flat':
            return path_split[0]
        else:
            assert False, 'Not Reachable'  # pragma: no cover
