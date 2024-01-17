from __future__ import annotations

from pathlib import Path

import pytest

from checker.configs import CheckerExportConfig, CheckerStructureConfig, DeadlinesConfig
from checker.course import Course
from checker.exceptions import BadConfig
from checker.exporter import Exporter

from .conftest import T_GENERATE_FILE_STRUCTURE


def assert_files_in_folder(folder: Path, expected_files: list[str]) -> None:
    # check if all expected files are in folder
    for file in expected_files:
        assert (folder / file).exists(), f"File {file} not found in {folder}"
    # check no other files are in folder
    for file in folder.glob("**/*"):
        if file.is_dir():
            continue
        assert str(file.relative_to(folder)) in expected_files, f"File {file.relative_to(folder)} not expected"


# TODO: extend tests
class TestExporter:
    SAMPLE_TEST_DEADLINES_CONFIG = DeadlinesConfig(
        version=1,
        settings={"timezone": "Europe/Berlin"},
        schedule=[
            {
                "group": "group",
                "enabled": True,
                "start": "2021-01-01 00:00:00",
                "tasks": [
                    {"task": "task1", "score": 1},
                    {"task": "task2", "score": 1},
                    {"task": "task3", "enabled": False, "score": 1},
                ],
            },
            {
                "group": "disabled_group",
                "enabled": False,
                "start": "2021-01-01 00:00:00",
                "tasks": [
                    {"task": "task_disabled_1", "score": 1},
                    {"task": "task_disabled_2", "enabled": True, "score": 1},
                ],
            },
            {
                "group": "no_folder_group",
                "enabled": True,
                "start": "2021-01-01 00:00:00",
                "tasks": [{"task": "root_task_1", "score": 1}],
            },
        ],
    )
    SAMPLE_TEST_STRUCTURE_CONFIG = CheckerStructureConfig(
        ignore_patterns=[".ignore_folder"],
        public_patterns=[".private_exception", ".group.yml"],  # note: .task.yml ignored by default
        private_patterns=[".*", "private.*"],
    )
    SAMPLE_TEST_FILES = {
        ".ignore_folder": {
            "folder": {
                "test.txt": "Hello2\n",
                "test.py": "print('Hello2')\n",
            },
        },
        ".private_folder": {
            "test.txt": "Hello3\n",
            "folder": {
                ".test.py": "print('Hello3')\n",
                "test.txt": "Hello4\n",
            },
        },
        "folder": {
            "test.txt": "Hello2\n",
            ".test.py": "print('Hello2')\n",
            "folder": {
                "test.txt": "Hello2\n",
            },
        },
        "other_folder": {
            "test.txt": "Hello5\n",
        },
        "group": {
            "task1": {
                ".task.yml": "version: 1\nstructure:\n    private_patterns: []\n",
                "test.txt": "Hello\n",
                ".test.py": "print('Hello')\n",  # not private anymore, override
            },
            "task2": {
                "junk_group_folder": {"some_junk_file.txt": "Junk\n"},
                ".task.yml": "version: 1",
                "private.txt": "Private\n",
                "private.py": "print('Private')\n",
                "valid.txt": "Valid\n",
            },
            "junk_file.py": "123",
            ".group.yml": "version: 1\nstructure:\n    ignore_patterns: [junk_group_folder, junk_file.py]\n",
        },
        "root_task_1": {
            ".task.yml": "version: 1\nstructure:\n    public_patterns: []\n",
            ".private_exception": "Some line\n",  # not public anymore, override
            "test.txt": "Hello\n",
        },
        "test.py": "print('Hello')\n",
        "test.txt": "Hello\n",
        ".some_file": "Some line\n",
        ".private_exception": "Some line\n",
        "private.txt": "Private\n",
        "private.py": "print('Private')\n",
    }

    def test_validate_ok_no_task_configs(
        self, tmpdir: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE
    ) -> None:
        structure_config = CheckerStructureConfig(
            ignore_patterns=[".gitignore"],
            private_patterns=[".*"],
            public_patterns=["*"],
        )
        generate_file_structure(
            {
                "folder": {"test.txt": "Hello\n"},
                "test.py": "print('Hello')\n",
            },
            root=Path(tmpdir / "repository"),
        )
        course = Course(
            deadlines=self.SAMPLE_TEST_DEADLINES_CONFIG,
            repository_root=Path(tmpdir / "repository"),
        )
        exporter = Exporter(
            course,
            structure_config,
            CheckerExportConfig(destination="https://example.com"),
            Path(tmpdir / "repository"),
        )
        exporter.validate()

    def test_validate_ok_task_configs(self, tmpdir: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE) -> None:
        structure_config = CheckerStructureConfig(
            ignore_patterns=[".gitignore"],
            private_patterns=[".*"],
            public_patterns=["*"],
        )
        generate_file_structure(
            {
                "folder": {".task.yml": "version: 1\n", "test.txt": "Hello\n"},
                "test.py": "print('Hello')\n",
            },
            root=Path(tmpdir / "repository"),
        )
        course = Course(
            deadlines=self.SAMPLE_TEST_DEADLINES_CONFIG,
            repository_root=Path(tmpdir / "repository"),
        )
        exporter = Exporter(
            course,
            structure_config,
            CheckerExportConfig(destination="https://example.com"),
            Path(tmpdir / "repository"),
        )

        exporter.validate()

    def test_validate_fail_wrong_task_config(
        self, tmpdir: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE
    ) -> None:
        _ = CheckerStructureConfig(
            ignore_patterns=[".gitignore"],
            private_patterns=[".*"],
            public_patterns=["*"],
        )
        generate_file_structure(
            {
                "folder": {".task.yml": "wrong_field: HEHE\n", "test.txt": "Hello\n"},
                "test.py": "print('Hello')\n",
            },
            root=Path(tmpdir / "repository"),
        )
        with pytest.raises(BadConfig):
            course = Course(
                deadlines=self.SAMPLE_TEST_DEADLINES_CONFIG,
                repository_root=Path(tmpdir / "repository"),
            )
            course.validate()

        # exporter = Exporter(
        #     course,
        #     structure_config,
        #     CheckerExportConfig(destination="https://example.com"),
        #     Path(tmpdir / "repository"),
        # )
        # with pytest.raises(BadConfig):
        #     exporter.validate()

    def test_export_public(self, tmpdir: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE) -> None:
        generate_file_structure(self.SAMPLE_TEST_FILES, root=Path(tmpdir / "repository"))
        course = Course(
            deadlines=self.SAMPLE_TEST_DEADLINES_CONFIG,
            repository_root=Path(tmpdir / "repository"),
        )
        exporter = Exporter(
            course,
            self.SAMPLE_TEST_STRUCTURE_CONFIG,
            CheckerExportConfig(destination="https://example.com"),
            Path(tmpdir / "repository"),
        )

        exporter.export_public(Path(tmpdir / "export"))

        assert_files_in_folder(
            Path(tmpdir / "export").resolve(),
            [
                "folder/test.txt",
                "folder/folder/test.txt",
                "other_folder/test.txt",
                "test.py",
                "test.txt",
                ".private_exception",
                "group/task1/.task.yml",
                "group/task1/test.txt",
                "group/task1/.test.py",
                "group/task2/valid.txt",
                "group/.group.yml",
                "root_task_1/test.txt",
            ],
        )

    def test_export_for_testing(self, tmpdir: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE) -> None:
        generate_file_structure(self.SAMPLE_TEST_FILES, root=Path(tmpdir / "repository"))
        course = Course(
            deadlines=self.SAMPLE_TEST_DEADLINES_CONFIG,
            repository_root=Path(tmpdir / "repository"),
        )
        exporter = Exporter(
            course,
            self.SAMPLE_TEST_STRUCTURE_CONFIG,
            CheckerExportConfig(destination="https://example.com"),
            Path(tmpdir / "repository"),
        )

        exporter.export_for_testing(Path(tmpdir / "export"))

        assert_files_in_folder(
            Path(tmpdir / "export").resolve(),
            [
                ".private_folder/test.txt",
                ".private_folder/folder/.test.py",
                ".private_folder/folder/test.txt",
                "folder/test.txt",
                "folder/.test.py",
                "folder/folder/test.txt",
                "other_folder/test.txt",
                "test.py",
                "test.txt",
                ".some_file",
                ".private_exception",
                "private.txt",
                "private.py",
                "group/task1/.task.yml",
                "group/task1/test.txt",
                "group/task1/.test.py",
                "group/task2/.task.yml",
                "group/task2/private.txt",
                "group/task2/private.py",
                "group/task2/valid.txt",
                "group/.group.yml",
                "root_task_1/.task.yml",
                "root_task_1/test.txt",
                "root_task_1/.private_exception",
            ],
        )

    def test_export_for_contribution(self, tmpdir: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE) -> None:
        generate_file_structure(self.SAMPLE_TEST_FILES, root=Path(tmpdir / "repository"))
        course = Course(
            deadlines=self.SAMPLE_TEST_DEADLINES_CONFIG,
            repository_root=Path(tmpdir / "repository"),
        )
        exporter = Exporter(
            course,
            self.SAMPLE_TEST_STRUCTURE_CONFIG,
            CheckerExportConfig(destination="https://example.com"),
            Path(tmpdir / "repository"),
        )

        exporter.export_for_contribution(Path(tmpdir / "export"))

        assert_files_in_folder(
            Path(tmpdir / "export").resolve(),
            [
                ".private_folder/test.txt",
                ".private_folder/folder/.test.py",
                ".private_folder/folder/test.txt",
                "folder/test.txt",
                "folder/.test.py",
                "folder/folder/test.txt",
                "other_folder/test.txt",
                "test.py",
                "test.txt",
                ".some_file",
                ".private_exception",
                "private.txt",
                "private.py",
                "group/task1/.task.yml",
                "group/task1/test.txt",
                "group/task1/.test.py",
                "group/task2/.task.yml",
                "group/task2/private.txt",
                "group/task2/private.py",
                "group/task2/valid.txt",
                "group/.group.yml",
                "root_task_1/.task.yml",
                "root_task_1/test.txt",
                "root_task_1/.private_exception",
            ],
        )
