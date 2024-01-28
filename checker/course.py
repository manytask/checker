from __future__ import annotations

import warnings
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import git

from .configs import CheckerSubConfig, CheckerTestingConfig, ManytaskConfig
from .exceptions import BadConfig, CheckerException
from .utils import print_info


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
        manytask_config: ManytaskConfig,
        repository_root: Path,
        reference_root: Path | None = None,
    ):
        self.manytask_config = manytask_config

        self.repository_root = repository_root
        self.reference_root = reference_root or repository_root

        self.potential_groups = {group.name: group for group in self._search_for_groups_by_configs(self.reference_root)}
        self.potential_tasks = {task.name: task for task in self._search_for_tasks_by_configs(self.reference_root)}

    def validate(self) -> None:
        # check all groups and tasks mentioned in deadlines exists
        deadlines_groups = self.manytask_config.get_groups(enabled=True)
        for deadline_group in deadlines_groups:
            if deadline_group.name not in self.potential_groups:
                warnings.warn(f"Group {deadline_group.name} not found in repository")

        deadlines_tasks = self.manytask_config.get_tasks(enabled=True)
        for deadlines_task in deadlines_tasks:
            if deadlines_task.name not in self.potential_tasks:
                raise BadConfig(f"Task {deadlines_task.name} not found in repository")

    def get_groups(
        self,
        enabled: bool | None = None,
    ) -> list[FileSystemGroup]:
        search_deadlines_groups = self.manytask_config.get_groups(enabled=enabled)

        return [
            self.potential_groups[deadline_group.name]
            for deadline_group in search_deadlines_groups
            if deadline_group.name in self.potential_groups
        ]

    def get_tasks(
        self,
        enabled: bool | None = None,
    ) -> list[FileSystemTask]:
        search_deadlines_tasks = self.manytask_config.get_tasks(enabled=enabled)

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
            if task_config_path.read_text().strip() == "":
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

    def detect_changes(
        self,
        detection_type: CheckerTestingConfig.ChangesDetectionType,
    ) -> list[FileSystemTask]:
        """
        Detects changes in the repository based on the provided detection type.

        :param detection_type: detection type, see CheckerTestingConfig.ChangesDetectionType
            - BRANCH_NAME: task name == branch name (single task/group)
            - COMMIT_MESSAGE: task name in commit message (can be multiple tasks/groups)
            - LAST_COMMIT_CHANGES: task relative path in last commit changes (can be multiple tasks)
        :return: list of changed tasks
        :raises CheckerException: if repository is not a git repository
        """
        print_info(f"Detecting changes by {detection_type}")
        potential_tasks = self.get_tasks(enabled=True)
        enabled_groups = self.manytask_config.get_groups(
            enabled=True
        )  # 'cause we want to check no-folder groups as well

        try:
            repo = git.Repo(self.repository_root)
        except git.exc.InvalidGitRepositoryError:
            raise CheckerException(f"Git Repository in {self.repository_root} not found")

        if detection_type == CheckerTestingConfig.ChangesDetectionType.BRANCH_NAME:
            branch_name = repo.active_branch.name
            print_info(f"Branch name: {branch_name}", color="grey")

            # try to get groups first
            changed_enabled_groups = [group for group in enabled_groups if group.name == branch_name]
            if changed_enabled_groups:
                print_info(f"Changed groups: {changed_enabled_groups} (branch name == group name)", color="grey")
                changed_enabled_tasks_names = {task.name for group in changed_enabled_groups for task in group.tasks}
                changed_tasks = [task for task in potential_tasks if task.name in changed_enabled_tasks_names]
                print_info(f"Changed tasks: {changed_tasks} (branch name == group name)", color="grey")
                return changed_tasks

            # if no groups found, try to get tasks
            changed_tasks = [task for task in potential_tasks if task.name == branch_name]
            print_info(f"Changed tasks: {changed_tasks} (branch name == task/group name)", color="grey")
            if not changed_tasks:
                print_info(f"No active task/group found for branch {branch_name}", color="yellow")

            return changed_tasks

        elif detection_type == CheckerTestingConfig.ChangesDetectionType.COMMIT_MESSAGE:
            commit_message = repo.head.commit.message
            if isinstance(commit_message, bytes):  # pragma: no cover
                commit_message = commit_message.decode("utf-8")
            print_info(f"Commit message: {commit_message}", color="grey")

            # try to get groups first
            changed_enabled_groups = [group for group in enabled_groups if group.name in commit_message]
            if changed_enabled_groups:
                print_info(f"Changed groups: {changed_enabled_groups} (group name in commit message)", color="grey")
                changed_enabled_tasks_names = {task.name for group in changed_enabled_groups for task in group.tasks}
                changed_tasks = [task for task in potential_tasks if task.name in changed_enabled_tasks_names]
                print_info(f"Changed tasks: {changed_tasks} (group name in commit message)", color="grey")
                return changed_tasks

            # if no groups found, try to get tasks
            changed_tasks = [task for task in potential_tasks if task.name in commit_message]
            print_info(f"Changed tasks: {changed_tasks} (task name in commit message)", color="grey")
            if not changed_tasks:
                print_info(f"No active tasks/groups found for commit message {commit_message}", color="yellow")

            return changed_tasks

        elif detection_type == CheckerTestingConfig.ChangesDetectionType.LAST_COMMIT_CHANGES:
            last_commit = repo.head.commit
            changed_files = [item.a_path for item in last_commit.diff("HEAD~1")]
            print_info(f"Last commit changes: {changed_files}", color="grey")

            changed_tasks = [
                task for task in potential_tasks if any(task.relative_path in file for file in changed_files)
            ]
            print_info(f"Changed tasks: {changed_tasks} (changed files in last commit)", color="grey")
            if not changed_tasks:
                warnings.warn(f"No active tasks found for last commit changes {changed_files}")

            return changed_tasks

        else:  # pragma: no cover
            assert False, "Unreachable code"
