from __future__ import annotations

import warnings
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .configs import CheckerSubConfig, DeadlinesConfig
from .exceptions import BadConfig


@dataclass
class FileSystemTask:
    name: str
    relative_path: str
    config: CheckerSubConfig


@dataclass
class FileSystemGroup:
    name: str
    relative_path: str
    config: CheckerSubConfig
    tasks: list[FileSystemTask]


class Course:
    """
    Class operates deadlines (filter, search etc), timezones and mapping tasks and groups to file system.
    Only operates with tasks and groups existing in file system.
    """

    TASK_CONFIG_NAME = ".task.yml"
    GROUP_CONFIG_NAME = ".group.yml"

    def __init__(
        self,
        deadlines: DeadlinesConfig,
        repository_root: Path,
        reference_root: Path | None = None,
    ):
        self.deadlines = deadlines

        self.repository_root = repository_root
        self.reference_root = reference_root or repository_root

        self.potential_groups = {
            group.name: group for group in self._search_for_groups_by_configs(self.repository_root)
        }
        self.potential_tasks = {task.name: task for task in self._search_for_tasks_by_configs(self.repository_root)}

    def validate(self) -> None:
        # check all groups and tasks mentioned in deadlines exists
        deadlines_groups = self.deadlines.get_groups(enabled=True)
        for deadline_group in deadlines_groups:
            if deadline_group.name not in self.potential_groups:
                warnings.warn(f"Group {deadline_group.name} not found in repository")

        deadlines_tasks = self.deadlines.get_tasks(enabled=True)
        for deadlines_task in deadlines_tasks:
            if deadlines_task.name not in self.potential_tasks:
                raise BadConfig(f"Task {deadlines_task.name} of not found in repository")

    def get_groups(
        self,
        enabled: bool | None = None,
    ) -> list[FileSystemGroup]:
        search_deadlines_groups = self.deadlines.get_groups(enabled=enabled)

        return [
            self.potential_groups[deadline_group.name]
            for deadline_group in search_deadlines_groups
            if deadline_group.name in self.potential_groups
        ]

    def get_tasks(
        self,
        enabled: bool | None = None,
    ) -> list[FileSystemTask]:
        search_deadlines_tasks = self.deadlines.get_tasks(enabled=enabled)

        return [
            self.potential_tasks[deadline_task.name]
            for deadline_task in search_deadlines_tasks
            if deadline_task.name in self.potential_tasks
        ]

    @staticmethod
    def _search_for_tasks_by_configs(
        root: Path,
    ) -> Generator[FileSystemTask, Any, None]:
        for task_config_path in root.glob(f"**/{Course.TASK_CONFIG_NAME}"):
            relative_task_path = task_config_path.parent.relative_to(root)

            # if empty file - use default
            if task_config_path.read_text().strip() == "" or task_config_path.read_text().strip() == "\n":
                task_config = CheckerSubConfig.default()
            # if any content - read yml
            else:
                task_config = CheckerSubConfig.from_yaml(task_config_path)

            yield FileSystemTask(
                name=task_config_path.parent.name,
                relative_path=str(relative_task_path),
                config=task_config,
            )

    @staticmethod
    def _search_for_groups_by_configs(
        root: Path,
    ) -> Generator[FileSystemGroup, Any, None]:
        for group_config_path in root.glob(f"**/{Course.GROUP_CONFIG_NAME}"):
            relative_group_path = group_config_path.parent.relative_to(root)

            # if empty file - use default
            if group_config_path.read_text().strip() == "" or group_config_path.read_text().strip() == "\n":
                group_config = CheckerSubConfig.default()
            # if any content - read yml
            else:
                group_config = CheckerSubConfig.from_yaml(group_config_path)

            group_tasks = list(Course._search_for_tasks_by_configs(group_config_path.parent))
            for task in group_tasks:
                task.relative_path = str(relative_group_path / task.relative_path)

            yield FileSystemGroup(
                name=group_config_path.parent.name,
                relative_path=str(relative_group_path),
                config=group_config,
                tasks=group_tasks,
            )
