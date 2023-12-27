from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Iterable

from checker.configs import CheckerExportConfig, CheckerStructureConfig
from checker.course import Course


class Exporter:
    def __init__(
        self,
        course: Course,
        structure_config: CheckerStructureConfig,
        export_config: CheckerExportConfig,
        repository_root: Path,
        reference_root: Path | None = None,
        *,
        cleanup: bool = True,
        verbose: bool = False,
        dry_run: bool = False,
    ) -> None:
        self.course = course

        self.structure_config = structure_config
        self.export_config = export_config

        self.repository_root = repository_root
        self.reference_root = reference_root or repository_root

        self._temporary_dir_manager = tempfile.TemporaryDirectory()
        self.temporary_dir = Path(self._temporary_dir_manager.name)

        self.cleanup = cleanup
        self.verbose = verbose
        self.dry_run = dry_run

    def validate(self) -> None:
        # TODO: implement validation
        pass

    def export_public(
        self,
        target: Path,
        push: bool = False,
        commit_message: str = "chore(auto): Update public files [skip-ci]",
    ) -> None:
        target.mkdir(parents=True, exist_ok=True)

        tasks = self.course.get_tasks(enabled=True)

        global_ignore_patterns = self.structure_config.ignore_patterns or []
        global_public_patterns = self.structure_config.public_patterns or []
        global_private_patterns = self.structure_config.private_patterns or []

        # TODO: implement template searcher

        print("REFERENCE")
        print(f"Copy files from {self.reference_root} to {target}")
        self._copy_files_accounting_sub_rules(
            self.reference_root,
            target,
            search_pattern="*",
            copy_patterns=[
                "*",
                *global_public_patterns,
            ],
            ignore_patterns=[
                *global_private_patterns,
                *global_ignore_patterns,
            ],
            sub_rules={
                self.reference_root
                / task.relative_path: (
                    [
                        "*",
                        *(
                            task_ignore
                            if (task_ignore := task.config.structure.public_patterns) is not None
                            else global_public_patterns
                        ),
                    ],
                    [
                        *(
                            task_ignore
                            if (task_ignore := task.config.structure.private_patterns) is not None
                            else global_private_patterns
                        ),
                        *(
                            task_ignore
                            if (task_ignore := task.config.structure.ignore_patterns) is not None
                            else global_ignore_patterns
                        ),
                    ],
                )
                for task in tasks
                if task.config is not None and task.config.structure is not None
            },
        )

    def export_for_testing(
        self,
        target: Path,
    ) -> None:
        target.mkdir(parents=True, exist_ok=True)

        tasks = self.course.get_tasks(enabled=True)

        global_ignore_patterns = self.structure_config.ignore_patterns or []
        global_public_patterns = self.structure_config.public_patterns or []
        global_private_patterns = self.structure_config.private_patterns or []

        print("REPO")
        print(f"Copy files from {self.repository_root} to {target}")
        self._copy_files_accounting_sub_rules(
            self.repository_root,
            target,
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
                            if (task_ignore := task.config.structure.ignore_patterns) is not None
                            else global_ignore_patterns
                        ),
                        *(
                            task_public
                            if (task_public := task.config.structure.public_patterns) is not None
                            else global_public_patterns
                        ),
                        *(
                            task_private
                            if (task_private := task.config.structure.private_patterns) is not None
                            else global_private_patterns
                        ),
                    ],
                )
                for task in tasks
                if task.config is not None and task.config.structure is not None
            },
        )

        print("REFERENCE")
        print(f"Copy files from {self.reference_root} to {target}")
        self._copy_files_accounting_sub_rules(
            self.reference_root,
            target,
            search_pattern="*",
            copy_patterns=[
                *global_public_patterns,
                *global_private_patterns,
            ],
            ignore_patterns=[
                *global_ignore_patterns,
            ],
            sub_rules={
                self.reference_root
                / task.relative_path: (
                    [
                        *(
                            task_public
                            if (task_public := task.config.structure.public_patterns) is not None
                            else global_public_patterns
                        ),
                        *(
                            task_private
                            if (task_private := task.config.structure.private_patterns) is not None
                            else global_private_patterns
                        ),
                    ],
                    [
                        *(
                            task_ignore
                            if (task_ignore := task.config.structure.ignore_patterns) is not None
                            else global_ignore_patterns
                        ),
                    ],
                )
                for task in tasks
                if task.config is not None and task.config.structure is not None
            },
        )

    def export_for_contribution(
        self,
        target: Path,
    ) -> None:
        target.mkdir(parents=True, exist_ok=True)

        tasks = self.course.get_tasks(enabled=True)

        global_ignore_patterns = self.structure_config.ignore_patterns or []
        global_public_patterns = self.structure_config.public_patterns or []
        global_private_patterns = self.structure_config.private_patterns or []  # noqa: F841

        print("REPO")
        print(f"Copy files from {self.repository_root} to {target}")
        self._copy_files_accounting_sub_rules(
            self.repository_root,
            target,
            search_pattern="*",
            copy_patterns=[
                *global_public_patterns,
            ],
            ignore_patterns=[
                *global_ignore_patterns,
            ],
            sub_rules={
                self.repository_root
                / task.relative_path: (
                    [
                        *(
                            task_public
                            if (task_public := task.config.structure.public_patterns) is not None
                            else global_public_patterns
                        ),
                    ],
                    [
                        *(
                            task_ignore
                            if (task_ignore := task.config.structure.ignore_patterns) is not None
                            else global_ignore_patterns
                        ),
                    ],
                )
                for task in tasks
                if task.config is not None and task.config.structure is not None
            },
        )

        print("REFERENCE")
        print(f"Copy files from {self.reference_root} to {target}")
        self._copy_files_accounting_sub_rules(
            self.reference_root,
            target,
            search_pattern="*",
            copy_patterns=["*"],
            ignore_patterns=[
                *global_public_patterns,
                *global_ignore_patterns,
            ],
            sub_rules={
                self.reference_root
                / task.relative_path: (
                    ["*"],
                    [
                        *(
                            task_ignore
                            if (task_ignore := task.config.structure.public_patterns) is not None
                            else global_public_patterns
                        ),
                        *(
                            task_ignore
                            if (task_ignore := task.config.structure.ignore_patterns) is not None
                            else global_ignore_patterns
                        ),
                    ],
                )
                for task in tasks
                if task.config is not None and task.config.structure is not None
            },
        )

    def _copy_files_accounting_sub_rules(
        self,
        root: Path,
        destination: Path,
        search_pattern: str,
        copy_patterns: Iterable[str],
        ignore_patterns: Iterable[str],
        sub_rules: dict[Path, tuple[Iterable[str], Iterable[str]]],
    ) -> None:
        """
        Copy files as usual, if face some folder from `sub_rules`, apply patterns from `sub_rules[folder]`.
        :param root: Copy files from this directory
        :param destination: Copy files to this directory
        :param search_pattern: Glob pattern to search files (then apply to ignore or copy)
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
                    print(f"    - Check Dir {path} to {destination / relative_filename} with sub rules (rec)")
                    self._copy_files_accounting_sub_rules(
                        path,
                        destination / relative_filename,
                        search_pattern="*",
                        copy_patterns=sub_rules[path][0],
                        ignore_patterns=sub_rules[path][1],
                        sub_rules=sub_rules,
                    )
                else:
                    print(f"    - Check Dir {path} to {destination / relative_filename} (rec)")
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
                    print(f"    - Copy File {path} to {destination / relative_filename}")
                    destination.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(
                        path,
                        destination / relative_filename,
                    )

    def __del__(self) -> None:
        if self.__dict__.get("cleanup") and self._temporary_dir_manager:
            self._temporary_dir_manager.cleanup()
