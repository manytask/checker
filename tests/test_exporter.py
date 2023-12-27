from __future__ import annotations

from inspect import cleandoc
from pathlib import Path

import pytest

from checker.configs import CheckerExportConfig, CheckerStructureConfig, DeadlinesConfig
from checker.course import Course
from checker.exceptions import BadConfig
from checker.exporter import Exporter


def create_test_files(tmpdir: Path, files_content: dict[str, str]) -> None:
    for filename, content in files_content.items():
        file = Path(tmpdir / filename)
        file.parent.mkdir(parents=True, exist_ok=True)
        with open(file, "w") as f:
            f.write(cleandoc(content))


def assert_files_in_folder(folder: Path, expected_files: list[str]) -> None:
    for file in expected_files:
        assert (folder / file).exists()


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
                "tasks": [{"task": "task1", "score": 1}, {"task": "task2", "score": 1}],
            },
        ],
    )
    SAMPLE_TEST_STRUCTURE_CONFIG = CheckerStructureConfig(
        ignore_patterns=[".ignore_folder"],
        private_patterns=[".*", "private.*"],
        public_patterns=["*", ".private_exception"],
    )
    SAMPLE_TEST_FILES = {
        ".ignore_folder/test.txt": "Hello1\n",
        ".ignore_folder/folder/test.txt": "Hello2\n",
        ".ignore_folder/folder/test.py": "print('Hello2')\n",
        "folder/test.txt": "Hello2\n",
        "folder/.test.py": "print('Hello2')\n",
        "folder/folder/test.txt": "Hello2\n",
        ".private_folder/test.txt": "Hello3\n",
        ".private_folder/folder/.test.py": "print('Hello3')\n",
        ".private_folder/folder/test.txt": "Hello4\n",
        "other_folder/test.txt": "Hello5\n",
        "test.py": "print('Hello')\n",
        "test.txt": "Hello\n",
        ".some_file": "Some line\n",
        ".private_exception": "Some line\n",
        "private.txt": "Private\n",
        "private.py": "print('Private')\n",
        "group/task1/.task.yml": "version: 1\nstructure:\n    private_patterns: []\n",
        "group/task1/test.txt": "Hello\n",
        "group/task1/.test.py": "print('Hello')\n",
        "group/task2/private.txt": "Private\n",
        "group/task2/private.py": "print('Private')\n",
        "group/task2/valid.txt": "Valid\n",
    }

    def test_validate_ok_no_task_configs(self, tmpdir: Path) -> None:
        structure_config = CheckerStructureConfig(
            ignore_patterns=[".gitignore"],
            private_patterns=[".*"],
            public_patterns=["*"],
        )
        create_test_files(
            Path(tmpdir / "repository"),
            {
                "test.py": "print('Hello')\n",
                "folder/test.txt": "Hello\n",
            },
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

    def test_validate_ok_task_configs(self, tmpdir: Path) -> None:
        structure_config = CheckerStructureConfig(
            ignore_patterns=[".gitignore"],
            private_patterns=[".*"],
            public_patterns=["*"],
        )
        create_test_files(
            Path(tmpdir / "repository"),
            {
                "test.py": "print('Hello')\n",
                "folder/.task.yml": "version: 1\n",
                "folder/test.txt": "Hello\n",
            },
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

    def test_validate_fail_wrong_task_config(self, tmpdir: Path) -> None:
        structure_config = CheckerStructureConfig(
            ignore_patterns=[".gitignore"],
            private_patterns=[".*"],
            public_patterns=["*"],
        )
        create_test_files(
            Path(tmpdir / "repository"),
            {
                "test.py": "print('Hello')\n",
                "folder/.task.yml": "wrong_field: HEHE\n",
                "folder/test.txt": "Hello\n",
            },
        )
        course = Course(
            deadlines=self.SAMPLE_TEST_DEADLINES_CONFIG,
            repository_root=Path(tmpdir / "repository"),
        )
        with pytest.raises(BadConfig):
            course.validate()
        exporter = Exporter(
            course,
            structure_config,
            CheckerExportConfig(destination="https://example.com"),
            Path(tmpdir / "repository"),
        )

        exporter.validate()

    def test_export_public(self, tmpdir: Path) -> None:
        create_test_files(Path(tmpdir / "repository"), self.SAMPLE_TEST_FILES)
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
            tmpdir / "export",
            [
                "folder/test.txt",
                "folder/folder/test.txt",
                "other_folder/test.txt",
                "test.py",
                "test.txt",
                # ".private_exception",  # TODO: fix private exception here not applied
                "group/task1/.task.yml",
                "group/task1/test.txt",
                "group/task1/.test.py",
                "group/task2/valid.txt",
            ],
        )

    def test_export_for_testing(self, tmpdir: Path) -> None:
        create_test_files(Path(tmpdir / "repository"), self.SAMPLE_TEST_FILES)
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
            tmpdir / "export",
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
            ],
        )

    def test_export_for_contribution(self, tmpdir: Path) -> None:
        create_test_files(Path(tmpdir / "repository"), self.SAMPLE_TEST_FILES)
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
            tmpdir / "export",
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
            ],
        )
