from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from checker.course import Course, FileSystemTask, FileSystemGroup
from checker.configs.deadlines import DeadlinesConfig
from checker.exceptions import BadConfig

TEST_TIMEZONE = "Europe/Berlin"
TEST_FILE_STRUCTURE = {
    "group1": {
        "task1_1": {".task.yml": "version: 1", "file1_1_1": "", "file1_1_2": ""},
        "task1_2": {"file1_2_1": "", "file1_2_2": ""},
    },
    "group2": {
        "task2_1": {"file2_1_1": "", "file2_1_2": ""},
        "task2_2": {".task.yml": "version: 1"},
        "task2_3": {"file2_3_1": "", "file2_3_2": "", "file2_3_3": "", "file2_3_4": ""},
    },
    "group3": {},
    "group4": {
        "task4_1": {".task.yml": "version: 1"},
    },
}
TEST_EXTRA_FILES = [
    "extra_file1",
    "group1/extra_file2",
    "group1/task1_1/extra_file3",
]
TEST_DEADLINES_CONFIG = DeadlinesConfig(
    version=1,
    settings={"timezone": TEST_TIMEZONE},
    schedule=[
        {"group": "group1", "start": "2020-10-10 00:00:00", "enabled": True, "tasks": [{"task": "task1_1", "score": 10}, {"task": "task1_2", "score": 20}]},
        {"group": "group2", "start": "2020-10-10 00:00:00", "enabled": False, "tasks": [{"task": "task2_1", "score": 30}, {"task": "task2_2", "score": 40}, {"task": "task2_3", "score": 50}]},
        {"group": "group3", "start": "2020-10-10 00:00:00", "enabled": True, "tasks": []},
        {"group": "group4", "start": "2020-10-10 00:00:00", "enabled": True, "tasks": [{"task": "task4_1", "score": 50}]},
    ],
)


@pytest.fixture()
def repository_root(tmp_path: Path) -> Path:
    """Creates a test repository structure in the temporary directory."""
    for group_name, group in TEST_FILE_STRUCTURE.items():
        group_path = tmp_path / group_name
        group_path.mkdir()
        for task_name, task in group.items():
            task_path = group_path / task_name
            task_path.mkdir()
            for filename, content in task.items():
                with open(task_path / filename, "w") as f:
                    f.write(content)

    for extra_file in TEST_EXTRA_FILES:
        with open(tmp_path / extra_file, "w") as f:
            f.write("")

    return tmp_path


class TestCourse:
    def test_init(self, repository_root: Path) -> None:
        test_course = Course(deadlines=TEST_DEADLINES_CONFIG, repository_root=repository_root)
        assert test_course.repository_root == repository_root
        assert test_course.deadlines == TEST_DEADLINES_CONFIG

    def test_validate(self, repository_root: Path) -> None:
        test_course = Course(deadlines=TEST_DEADLINES_CONFIG, repository_root=repository_root)

        try:
            test_course.validate()
        except Exception as e:
            pytest.fail(f"Validation failed: {e}")

    def test_validate_with_no_group(self, repository_root: Path) -> None:
        shutil.rmtree(repository_root / "group1")
        with pytest.raises(BadConfig):
            Course(deadlines=TEST_DEADLINES_CONFIG, repository_root=repository_root).validate()

    def test_validate_with_no_task(self, repository_root: Path) -> None:
        shutil.rmtree(repository_root / "group1" / "task1_1")
        with pytest.raises(BadConfig):
            Course(deadlines=TEST_DEADLINES_CONFIG, repository_root=repository_root).validate()

    def test_init_task_with_bad_config(self, repository_root: Path) -> None:
        with open(repository_root / "group1" / "task1_1" / Course.TASK_CONFIG_NAME, "w") as f:
            f.write("bad_config")

        with pytest.raises(BadConfig):
            Course(deadlines=TEST_DEADLINES_CONFIG, repository_root=repository_root)

    @pytest.mark.parametrize("enabled, expected_num_groups", [(None, 4), (True, 3), (False, 1)])
    def test_get_groups(self, enabled: bool | None, expected_num_groups, repository_root: Path) -> None:
        test_course = Course(deadlines=TEST_DEADLINES_CONFIG, repository_root=repository_root)

        groups = test_course.get_groups(enabled=enabled)
        assert isinstance(groups, list)
        assert all(isinstance(group, FileSystemGroup) for group in groups)
        assert len(groups) == expected_num_groups

    @pytest.mark.parametrize("enabled, expected_num_tasks", [(None, 6), (True, 3), pytest.param(False, 3, marks=pytest.mark.xfail())])
    def test_get_tasks(self, enabled: bool | None, expected_num_tasks, repository_root: Path) -> None:
        test_course = Course(deadlines=TEST_DEADLINES_CONFIG, repository_root=repository_root)

        tasks = test_course.get_tasks(enabled=enabled)
        assert isinstance(tasks, list)
        assert all(isinstance(task, FileSystemTask) for task in tasks)
        assert len(tasks) == expected_num_tasks

    def test_search_potential_groups(self, repository_root: Path) -> None:
        potential_groups = Course._search_potential_groups(repository_root)
        assert len(potential_groups) == len(TEST_FILE_STRUCTURE)
        for group in potential_groups:
            assert isinstance(group, FileSystemGroup)
            assert len(group.tasks) == len(TEST_FILE_STRUCTURE[group.name])
            for task in group.tasks:
                assert isinstance(task, FileSystemTask)
                assert (repository_root / task.relative_path).exists()

    def test_search_for_tasks_by_configs(self, repository_root: Path) -> None:
        tasks = list(Course._search_for_tasks_by_configs(repository_root))
        assert len(tasks) == 3
        for task in tasks:
            assert isinstance(task, FileSystemTask)
            assert (repository_root / task.relative_path).exists()
