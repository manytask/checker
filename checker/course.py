from __future__ import annotations

import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .configs import DeadlinesConfig, TaskConfig
from .configs.checker import CheckerConfig, CheckerParametersConfig
from .exceptions import BadConfig


@dataclass
class FileSystemTask:
    name: str
    relative_path: str
    config: TaskConfig | None = None


@dataclass
class FileSystemGroup:
    name: str
    relative_path: str
    tasks: list[FileSystemTask]


class Course:
    """
    Main point of the "physical" course.
    Class responsible for interaction with the file system directory.
    """

    def __init__(
        self,
        checker_config: CheckerConfig,
        deadlines_config: DeadlinesConfig,
        repository_root: Path,
        reference_root: Path | None = None,
        username: str | None = None,
    ):
        self.checker = checker_config
        self.deadlines = deadlines_config

        self.repository_root = repository_root
        self.reference_root = reference_root or repository_root

        self.username = username or "unknown"

        self.potential_groups = {
            group.name: group
            for group in self._search_potential_groups(self.repository_root)
        }
        self.potential_tasks = {
            task.name: task
            for group in self.potential_groups.values()
            for task in group.tasks
        }

    def validate(self) -> None:
        # check all groups and tasks mentioned in deadlines exists
        deadlines_groups = self.deadlines.get_groups(enabled=True)
        for deadline_group in deadlines_groups:
            if deadline_group.name not in self.potential_groups:
                raise BadConfig(f"Group {deadline_group.name} not found in repository")

        deadlines_tasks = self.deadlines.get_tasks(enabled=True)
        for deadlines_task in deadlines_tasks:
            if deadlines_task.name not in self.potential_tasks:
                raise BadConfig(
                    f"Task {deadlines_task.name} of not found in repository"
                )

    def _copy_files_accounting_sub_rules(
        self,
        root: Path,
        destination: Path,
        search_pattern: str,
        copy_patterns: Iterable[str],
        ignore_patterns: Iterable[str],
        sub_rules: dict[Path, tuple[Iterable[str], Iterable[str]]],
    ):
        """
        Copy files as usual, if face some folder from `sub_rules`, apply patterns from `sub_rules[folder]`.
        :param root: Copy files from this directory
        :param destination: Copy files to this directory
        :param search_pattern: Glob pattern to search files (then apply ignore or copy)
        :param copy_patterns: List of glob patterns to copy, None to have *. Apply recursively
        :param ignore_patterns: List of glob patterns to ignore, None to have []. Apply recursively
        :param sub_rules: dict of folder -> [patterns, ignore_patterns] to apply to this folder (and recursively)
        """
        copy_patterns = copy_patterns or ["*"]
        ignore_patterns = ignore_patterns or []

        for path in root.glob(search_pattern):
            # check if the file name matches the patterns
            if any(path.match(ignore_pattern) for ignore_pattern in ignore_patterns):
                print(f"    - Skip {path} because of ignore patterns")
                continue

            relative_filename = str(path.relative_to(root))
            if path.is_dir():
                if path in sub_rules:
                    print(
                        f"    - Check Dir {path} to {destination / relative_filename} with sub rules (rec)"
                    )
                    self._copy_files_accounting_sub_rules(
                        path,
                        destination / relative_filename,
                        search_pattern="*",
                        copy_patterns=sub_rules[path][0],
                        ignore_patterns=sub_rules[path][1],
                        sub_rules=sub_rules,
                    )
                else:
                    print(
                        f"    - Check Dir {path} to {destination / relative_filename} (rec)"
                    )
                    self._copy_files_accounting_sub_rules(
                        path,
                        destination / relative_filename,
                        search_pattern="*",
                        copy_patterns=copy_patterns,
                        ignore_patterns=ignore_patterns,
                        sub_rules=sub_rules,
                    )
            else:
                if any(path.match(copy_pattern) for copy_pattern in copy_patterns):
                    print(
                        f"    - Copy File {path} to {destination / relative_filename}"
                    )
                    destination.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(
                        path,
                        destination / relative_filename,
                    )

    def copy_files_for_testing(self, destination: Path) -> None:
        tasks = self.get_tasks(enabled=True)

        global_ignore_patterns = self.checker.structure.ignore_patterns or []
        global_public_patterns = self.checker.structure.public_patterns or []
        global_private_patterns = self.checker.structure.private_patterns or []

        print("REPO")
        print(f"Copy files from {self.repository_root} to {destination}")
        self._copy_files_accounting_sub_rules(
            self.repository_root,
            destination,
            search_pattern="*",
            copy_patterns=["*"],
            ignore_patterns=[
                *global_ignore_patterns,
                *global_public_patterns,
                *global_private_patterns,
            ],
            sub_rules={
                self.repository_root
                / task.relative_path: (
                    ["*"],
                    [
                        *(
                            task_ignore
                            if (task_ignore := task.config.structure.ignore_patterns)
                            is not None
                            else global_ignore_patterns
                        ),
                        *(
                            task_public
                            if (task_public := task.config.structure.public_patterns)
                            is not None
                            else global_public_patterns
                        ),
                        *(
                            task_private
                            if (task_private := task.config.structure.private_patterns)
                            is not None
                            else global_private_patterns
                        ),
                    ],
                )
                for task in tasks
                if task.config is not None and task.config.structure is not None
            },
        )

        print("REFERECNE")
        print(f"Copy files from {self.reference_root} to {destination}")
        self._copy_files_accounting_sub_rules(
            self.reference_root,
            destination,
            search_pattern="*",
            copy_patterns=[
                *global_public_patterns,
                *global_private_patterns,
            ],
            ignore_patterns=[
                *self.checker.structure.ignore_patterns,
            ],
            sub_rules={
                self.reference_root
                / task.relative_path: (
                    [
                        *(
                            task_public
                            if (task_public := task.config.structure.public_patterns)
                            is not None
                            else global_public_patterns
                        ),
                        *(
                            task_private
                            if (task_private := task.config.structure.private_patterns)
                            is not None
                            else global_private_patterns
                        ),
                    ],
                    [
                        *(
                            task_ignore
                            if (task_ignore := task.config.structure.ignore_patterns)
                            is not None
                            else global_ignore_patterns
                        ),
                    ],
                )
                for task in tasks
                if task.config is not None and task.config.structure is not None
            },
        )
        import os

        def list_files(startpath):
            for root, dirs, files in sorted(os.walk(startpath)):
                level = root.replace(startpath, "").count(os.sep)
                indent = " " * 4 * (level)
                print("{}{}/".format(indent, os.path.basename(root)))
                subindent = " " * 4 * (level + 1)
                for f in files:
                    print("{}{}".format(subindent, f))

        list_files(str(destination))

    def get_groups(
        self,
        enabled: bool | None = None,
    ) -> list[FileSystemGroup]:
        return [
            self.potential_groups[deadline_group.name]
            for deadline_group in self.deadlines.get_groups(enabled=enabled)
            if deadline_group.name in self.potential_groups
        ]

    def get_tasks(
        self,
        enabled: bool | None = None,
    ) -> list[FileSystemTask]:
        return [
            self.potential_tasks[deadline_task.name]
            for deadline_task in self.deadlines.get_tasks(enabled=enabled)
            if deadline_task.name in self.potential_tasks
        ]

    def _search_potential_groups(self, root: Path) -> list[FileSystemGroup]:
        # search in the format $GROUP_NAME/$TASK_NAME starting root
        potential_groups = []

        for group_path in root.iterdir():
            if not group_path.is_dir():
                continue

            potential_tasks = []

            for task_path in group_path.iterdir():
                if not task_path.is_dir():
                    continue

                task_config_path = task_path / ".task.yml"
                task_config: TaskConfig | None = None
                if task_config_path.exists():
                    try:
                        task_config = TaskConfig.from_yaml(task_config_path)
                    except BadConfig as e:
                        raise BadConfig(
                            f"Task config {task_config_path} is invalid:\n{e}"
                        )

                potential_tasks.append(
                    FileSystemTask(
                        name=task_path.name,
                        relative_path=str(task_path.relative_to(root)),
                        config=task_config,
                    )
                )

            potential_groups.append(
                FileSystemGroup(
                    name=group_path.name,
                    relative_path=str(group_path.relative_to(root)),
                    tasks=potential_tasks,
                )
            )
        return potential_groups

    def _search_for_tasks_by_configs(self, root: Path) -> list[FileSystemTask]:
        for task_config_path in root.glob(f"**/.task.yml"):
            task_config = TaskConfig.from_yaml(task_config_path)
            yield FileSystemTask(
                name=task_config.name,
                relative_path=str(task_config_path.parent.relative_to(root)),
                config=task_config,
            )

    def list_all_public_files(self, root: Path) -> list[Path]:
        # read global files
        glob_patterns = self.checker.structure.public_patterns
        global_files = [
            file for pattern in glob_patterns for file in root.glob(pattern)
        ]
        # remove all task directories, wi
        # filter with tasks specific configs
        task_files = [
            file
            for task in self.repository_tasks
            for pattern in task.config.structure.public_patterns
            for file in (root / task.relative_path).glob(pattern)
        ]
