from __future__ import annotations

import copy
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

        self.sub_config_files = {
            (self.repository_root / task.relative_path).resolve().relative_to(self.repository_root):
                task.config.structure
            for task in self.course.get_tasks(enabled=True)
            if task.config.structure
        }
        for i in self.sub_config_files:
            print(f"{i=} {self.sub_config_files[i]=}")

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

        print(f"Copy from {self.reference_root} to {target}")
        self._copy_files_with_config(
            self.reference_root,
            target,
            self.structure_config,
            copy_public=True,
            copy_private=False,
            copy_other=True,
        )

    def export_for_testing(
        self,
        target: Path,
    ) -> None:
        target.mkdir(parents=True, exist_ok=True)

        print(f"Copy from {self.repository_root} to {target}")
        self._copy_files_with_config(
            self.repository_root,
            target,
            self.structure_config,
            copy_public=False,
            copy_private=False,
            copy_other=True,
        )

        print(f"Copy from {self.reference_root} to {target}")
        self._copy_files_with_config(
            self.reference_root,
            target,
            self.structure_config,
            copy_public=True,
            copy_private=True,
            copy_other=False,
        )

    def export_for_contribution(
        self,
        target: Path,
    ) -> None:
        target.mkdir(parents=True, exist_ok=True)

        print(f"Copy from {self.repository_root} to {target}")
        self._copy_files_with_config(
            self.repository_root,
            target,
            self.structure_config,
            copy_public=True,
            copy_private=False,
            copy_other=True,
        )

        print(f"Copy from {self.reference_root} to {target}")
        self._copy_files_with_config(
            self.reference_root,
            target,
            self.structure_config,
            copy_public=False,
            copy_private=True,
            copy_other=True,
        )

    def _copy_files_with_config(
        self,
        root: Path,
        destination: Path,
        config: CheckerStructureConfig,
        copy_public: bool,
        copy_private: bool,
        copy_other: bool,
        global_root: Path = None,
        global_destination: Path = None,
    ) -> None:
        """
        Copy files from `root` to `destination` according to `config`.
        When face `sub_config_files`, apply it to the folder and all subfolders.

        :param root: Copy files from this directory
        :param destination: Copy files to this directory
        :param config: Config to apply to this folder (and recursively)
        :param copy_public: Copy public files
        :param copy_private: Copy private files
        :param copy_other: Copy other - not public and not private files
        :param global_root: Starting root directory
        :param global_destination: Starting destination directory
        """
        # TODO: implement template searcher

        global_root = global_root or root
        global_destination = global_destination or destination

        print(f"Copy files from <{root.relative_to(global_root)}> to <{destination.relative_to(global_destination)}>")
        print(f"  {config=}")

        # Iterate over all files in the root directory
        for path in root.iterdir():
            # print(f" - {path.relative_to(global_root)}")
            # ignore if match the patterns
            if config.ignore_patterns and any(path.match(ignore_pattern) for ignore_pattern in config.ignore_patterns):
                print(f"    - Skip <{path.relative_to(global_root)}> because ignore patterns=[{config.ignore_patterns}]")
                continue

            # If matches public patterns AND copy_public is False - skip
            is_public = False
            if config.public_patterns and any(path.match(public_pattern) for public_pattern in config.public_patterns):
                is_public = True
                if not copy_public:
                    print(f"    - Skip <{path.relative_to(global_root)}> because skip public_patterns=[{config.public_patterns}]")
                    continue

            # If matches private patterns AND copy_private is False - skip
            # If it is public file - never consider it as private
            is_private = False
            if not is_public and config.private_patterns and any(path.match(private_pattern) for private_pattern in config.private_patterns):
                is_private = True
                if not copy_private:
                    print(f"    - Skip <{path.relative_to(global_root)}> because skip private_patterns=[{config.private_patterns}]")
                    continue

            # if not match public and not match private and copy_other is False - skip
            # Note: never skip "other" directories, look inside them first
            if not is_public and not is_private and not path.is_dir():
                if not copy_other:
                    print(f"    - Skip <{path.relative_to(global_root)}> because skip other files not enabled")
                    continue

            # If the file is a directory, recursively call this function
            if path.is_dir():
                # if folder public or private - just copy it
                if is_public or is_private:
                    print(f"    - Fully Copy <{path.relative_to(global_root)}> to <{(destination / path.relative_to(root)).relative_to(global_destination)}>")
                    # TODO: think call recursive function with =True for all to apply ignore
                    # shutil.copytree(
                    #     path,
                    #     destination / path.relative_to(root),
                    # )
                    # continue
                    self._copy_files_with_config(
                        path,
                        destination / path.relative_to(root),
                        config,
                        copy_public=True,
                        copy_private=True,
                        copy_other=True,
                        global_root=global_root,
                        global_destination=global_destination,
                    )

                # If have sub-config - update config with sub-config
                if path.relative_to(global_root) in self.sub_config_files:
                    declared_sub_config = self.sub_config_files[path.relative_to(global_root)]
                    sub_config = CheckerStructureConfig(
                        ignore_patterns=declared_sub_config.ignore_patterns if declared_sub_config.ignore_patterns is not None else config.ignore_patterns,
                        private_patterns=declared_sub_config.private_patterns if declared_sub_config.private_patterns is not None else config.private_patterns,
                        public_patterns=declared_sub_config.public_patterns if declared_sub_config.public_patterns is not None else config.public_patterns,
                    )
                else:
                    sub_config = config

                # Recursively call this function
                print(f"    -- Recursively copy from <{path.relative_to(global_root)}> to <{(destination / path.relative_to(root)).relative_to(global_destination)}>")
                self._copy_files_with_config(
                    path,
                    destination / path.relative_to(root),
                    sub_config,
                    copy_public,
                    copy_private,
                    copy_other,
                    global_root=global_root,
                    global_destination=global_destination,
                )
            # If the file is a normal file, copy it
            else:
                print(f"    - Copy <{path.relative_to(global_root)}> to <{(destination / path.relative_to(root)).relative_to(global_destination)}>")
                (destination / path.relative_to(root)).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(
                    path,
                    destination / path.relative_to(root),
                )

    def __del__(self) -> None:
        if self.__dict__.get("cleanup") and self._temporary_dir_manager:
            self._temporary_dir_manager.cleanup()
