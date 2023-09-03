from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from checker.course import Group, Task
from checker.course.driver import CourseDriver
from checker.exceptions import BadConfig


DATA_FOLDER = Path(__file__).parents[1] / 'data' / 'driver'


@pytest.fixture(scope='function')
def test_group() -> Group:
    group = Group(
        name='test_group',
        start=datetime(2020, 1, 1),
        deadline=datetime(2020, 1, 2),
        second_deadline=datetime(2020, 1, 3),
        enabled=True,
        marked=False,
        tasks=[],
    )
    group.tasks.extend([
        Task(
            group=group,
            name=f'test_task_{i}',
            max_score=1,
            enabled=True,
            scoring_func='max',
            review=False,
            marked=False,
        )
        for i in range(5)
    ])
    return group

@pytest.fixture(scope='function')
def test_task(test_group: Group) -> Task:
    return test_group.tasks[0]


class TestDriver:

    @pytest.mark.parametrize('layout,location', [
        ('flat', 'tests'),
        ('groups', '.'),
        ('lectures', '.'),
    ])
    def test_deadlines_config(self, layout: str, location: str) -> None:
        driver = CourseDriver(Path(''), repo_type='private', layout=layout)
        assert driver.get_deadlines_file_path(raise_if_not_exists=False) == Path('') / location / '.deadlines.yml'

        with pytest.raises(BadConfig):
            driver.get_deadlines_file_path(raise_if_not_exists=True)

    def test_deadlines_not_in_public_repo(self) -> None:
        driver = CourseDriver(Path(''), repo_type='public', layout='flat')
        with pytest.raises(BadConfig):
            driver.get_deadlines_file_path(raise_if_not_exists=False)

    @pytest.mark.parametrize('repo_type,layout,location', [
        ('public', 'flat', None),
        ('private', 'flat', None),
        ('public', 'groups', 'lectures/test_group'),
        ('private', 'groups', 'lectures/test_group'),
        ('public', 'lectures', 'test_group/lecture'),
        ('private', 'lectures', 'test_group/lecture'),
    ])
    def test_get_lecture_dir(self, repo_type: str, layout: str, location: str | None, test_group: Group) -> None:
        driver = CourseDriver(Path(''), repo_type=repo_type, layout=layout)
        assert driver.get_group_lecture_dir(test_group, check_exists=False) == ((Path('') / location) if location else None)
        assert driver.get_group_lecture_dir(test_group, check_exists=True) is None

    @pytest.mark.parametrize('repo_type,layout,location', [
        ('public', 'flat', None),
        ('private', 'flat', None),
        ('public', 'groups', 'solutions/test_group'),
        ('private', 'groups', 'solutions/test_group'),
        ('public', 'lectures', 'test_group/review'),
        ('private', 'lectures', 'test_group/review'),
    ])
    def test_get_review_dir(self, repo_type: str, layout: str, location: str | None, test_group: Group) -> None:
        driver = CourseDriver(Path(''), repo_type=repo_type, layout=layout)
        assert driver.get_group_submissions_review_dir(test_group, check_exists=False) == ((Path('') / location) if location else None)
        assert driver.get_group_submissions_review_dir(test_group, check_exists=True) is None

    @pytest.mark.parametrize('repo_type,layout,location', [
        ('public', 'flat', None),
        ('private', 'flat', None),
        ('public', 'groups', 'test_group'),
        ('private', 'groups', 'test_group'),
        ('public', 'lectures', 'test_group'),
        ('private', 'lectures', 'test_group'),
    ])
    def test_get_group_dir(self, repo_type: str, layout: str, location: str | None, test_group: Group) -> None:
        driver = CourseDriver(Path(''), repo_type=repo_type, layout=layout)
        assert driver.get_group_dir(test_group, check_exists=False) == ((Path('') / location) if location else None)
        assert driver.get_group_dir(test_group, check_exists=True) is None

    @pytest.mark.parametrize('repo_type,layout,location', [
        ('public', 'flat', 'test_task_0'),
        ('private', 'flat', 'test_task_0'),
        ('public', 'groups', 'test_group/test_task_0'),
        ('private', 'groups', 'test_group/test_task_0'),
        ('public', 'lectures', 'test_group/tasks/test_task_0'),
        ('private', 'lectures', 'test_group/tasks/test_task_0'),
    ])
    def test_get_task_dir(self, repo_type: str, layout: str, location: str | None, test_task: Task) -> None:
        driver = CourseDriver(Path(''), repo_type=repo_type, layout=layout)
        assert driver.get_task_dir(test_task, check_exists=False) == ((Path('') / location) if location else None)
        assert driver.get_task_dir(test_task, check_exists=True) is None

    @pytest.mark.parametrize('repo_type,layout,location', [
        ('public', 'flat', 'test_task_0'),
        ('private', 'flat', 'tests/test_task_0'),
        ('public', 'groups', 'test_group/test_task_0'),
        ('private', 'groups', 'tests/test_group/test_task_0'),
        ('public', 'lectures', 'test_group/tasks/test_task_0'),
        ('private', 'lectures', 'test_group/tasks/test_task_0/solution'),
    ])
    def test_get_task_solution_dir(self, repo_type: str, layout: str, location: str | None, test_task: Task) -> None:
        driver = CourseDriver(Path(''), repo_type=repo_type, layout=layout)
        assert driver.get_task_solution_dir(test_task, check_exists=False) == ((Path('') / location) if location else None)
        assert driver.get_task_solution_dir(test_task, check_exists=True) is None

    @pytest.mark.parametrize('repo_type,layout,location', [
        ('public', 'flat', 'test_task_0'),
        ('private', 'flat', 'test_task_0'),
        ('public', 'groups', 'test_group/test_task_0'),
        ('private', 'groups', 'test_group/test_task_0'),
        ('public', 'lectures', 'test_group/tasks/test_task_0'),
        ('private', 'lectures', 'test_group/tasks/test_task_0/template'),
    ])
    def test_get_task_template_dir(self, repo_type: str, layout: str, location: str | None, test_task: Task) -> None:
        driver = CourseDriver(Path(''), repo_type=repo_type, layout=layout)
        assert driver.get_task_template_dir(test_task, check_exists=False) == ((Path('') / location) if location else None)
        assert driver.get_task_template_dir(test_task, check_exists=True) is None

    @pytest.mark.parametrize('repo_type,layout,location', [
        ('public', 'flat', 'test_task_0'),
        ('private', 'flat', 'test_task_0'),
        ('public', 'groups', 'test_group/test_task_0'),
        ('private', 'groups', 'test_group/test_task_0'),
        ('public', 'lectures', 'test_group/tasks/test_task_0'),
        ('private', 'lectures', 'test_group/tasks/test_task_0/public'),
    ])
    def test_get_task_public_test_dir(self, repo_type: str, layout: str, location: str | None, test_task: Task) -> None:
        driver = CourseDriver(Path(''), repo_type=repo_type, layout=layout)
        assert driver.get_task_public_test_dir(test_task, check_exists=False) == ((Path('') / location) if location else None)
        assert driver.get_task_public_test_dir(test_task, check_exists=True) is None

    @pytest.mark.parametrize('repo_type,layout,location', [
        ('public', 'flat', None),
        ('private', 'flat', 'tests/test_task_0'),
        ('public', 'groups', None),
        ('private', 'groups', 'tests/test_group/test_task_0'),
        ('public', 'lectures', None),
        ('private', 'lectures', 'test_group/tasks/test_task_0/private'),
    ])
    def test_get_task_private_test_dir(self, repo_type: str, layout: str, location: str | None, test_task: Task) -> None:
        driver = CourseDriver(Path(''), repo_type=repo_type, layout=layout)
        assert driver.get_task_private_test_dir(test_task, check_exists=False) == ((Path('') / location) if location else None)
        assert driver.get_task_private_test_dir(test_task, check_exists=True) is None

    @pytest.mark.parametrize('layout,raw,task_name', [
        ('flat', 'foo', None),
        ('flat', 'foo/bar', 'foo'),
        ('groups', 'foo/bar', 'bar'),
        ('lectures', 'foo/bar', 'bar'),
    ])
    def test_get_task_dir_name(self, layout: str, raw: str, task_name: str | None) -> None:
        driver = CourseDriver(Path(''), layout=layout)
        assert driver.get_task_dir_name(raw) == task_name
