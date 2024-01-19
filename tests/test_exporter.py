from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from checker.configs import CheckerExportConfig, CheckerStructureConfig, DeadlinesConfig
from checker.course import Course
from checker.exceptions import BadConfig, BadStructure
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


class TestExporterOnSimple:
    @pytest.fixture()
    def simple_deadlines(self) -> DeadlinesConfig:
        return DeadlinesConfig(
            version=1,
            settings={"timezone": "Europe/Berlin"},
            schedule=[
                {
                    "group": "no_folder_group",
                    "enabled": True,
                    "start": "2021-01-01 00:00:00",
                    "tasks": [
                        {"task": "task1", "score": 1},
                        {"task": "task2", "score": 1},
                    ],
                },
            ],
        )

    @pytest.fixture()
    def simple_structure(self) -> CheckerStructureConfig:
        return CheckerStructureConfig(
            ignore_patterns=[".ignore_me"],
            private_patterns=[".*"],
            public_patterns=["public*"],
        )

    @pytest.fixture()
    def simple_export_config(self) -> CheckerExportConfig:
        return CheckerExportConfig(
            destination="https://example.com",
            templates="search_or_create",
        )

    @pytest.fixture()
    def simple_private_layout(self, tmpdir: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE) -> Path:
        layout = {
            "task1": {".task.yml": "version: 1\nstructure:\n    ignore_patterns: [extra_ignore_me]\n", "test.txt": "Some TEMPLATE START\nHello\nTEMPLATE END\n", "public_file.py": "print('Hello')\n", "extra_ignore_me": ""},
            "task2": {".task.yml": "", "test.txt": "Some", "test.txt.template": "Will replace the file", ".private.file": "private\n"},
            ".ignore_me": "",
            "just_file": "hey",
            ".private.file": "private\n",
            "public_folder": {"file_in_public_folder": "file"},
            "public_file.py": "print('Hello')\n",
        }
        generate_file_structure(layout, Path(tmpdir / "repository"))
        return Path(tmpdir / "repository")

    @pytest.fixture()
    def simple_student_layout(self, tmpdir: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE) -> Path:
        layout = {
            "task1": {"test.txt": "Some Changes", "public_file.py": "print('Hello LOL this too')\n"},
            "task2": {"test.txt": "Student changed it"},
            "just_file": "hey",
            "public_folder": {"file_in_public_folder": "try to change"},
            "public_file.py": "print('Hello')\n",
        }
        generate_file_structure(layout, Path(tmpdir / "student"))
        return Path(tmpdir / "student")

    @pytest.fixture()
    def simple_exporter(
        self,
        tmpdir: Path,
        simple_private_layout: Path,
        simple_student_layout: Path,
        simple_deadlines: DeadlinesConfig,
        simple_structure: CheckerStructureConfig,
        simple_export_config: CheckerExportConfig,
    ) -> Exporter:
        course = Course(
            deadlines=simple_deadlines,
            repository_root=simple_student_layout,
            reference_root=simple_private_layout,
        )
        return Exporter(
            course,
            simple_structure,
            simple_export_config,
        )

    def test_simple_validate_ok(self, tmpdir: Path, simple_exporter: Exporter) -> None:
        simple_exporter.validate()

    def test_simple_validate_mix_templates_in_task(self, tmpdir: Path, simple_exporter: Exporter) -> None:
        # add other time to existing tasks
        Path(tmpdir / "repository" / "task1" / "new.txt").touch()
        Path(tmpdir / "repository" / "task1" / "new.txt.template").touch()
        Path(tmpdir / "repository" / "task2" / "new.txt").touch()
        Path(tmpdir / "repository" / "task2" / "new.txt").write_text("Some\n TEMPLATE START\nHello\nTEMPLATE END\n", encoding="utf-8")

        with pytest.raises(BadStructure) as exc_info:
            simple_exporter.validate()
        assert "use both" in str(exc_info.value)

    @pytest.mark.parametrize("template_type", [CheckerExportConfig.TemplateType.CREATE, CheckerExportConfig.TemplateType.SEARCH])
    def test_simple_validate_no_templates(self, tmpdir: Path, simple_exporter: Exporter, template_type: str) -> None:
        simple_exporter.export_config.templates = template_type

        # delete comment template, make wrong .template file
        Path(tmpdir / "repository" / "task1" / "test.txt").write_text("Some\n")
        Path(tmpdir / "repository" / "task2" / "not_original_file.txt.template").touch()

        with pytest.raises(BadStructure) as exc_info:
            simple_exporter.validate()
        assert "Have to include at least" in str(exc_info.value)

    @pytest.mark.parametrize("template_type", [CheckerExportConfig.TemplateType.SEARCH, CheckerExportConfig.TemplateType.SEARCH_OR_CREATE])
    def test_simple_validate_no_original_file_for_templates(self, tmpdir: Path, simple_exporter: Exporter, template_type: str) -> None:
        simple_exporter.export_config.templates = template_type

        # delete all templates files
        Path(tmpdir / "repository" / "task1" / "test.txt").unlink()
        Path(tmpdir / "repository" / "task1" / "test.txt.template").touch()

        with pytest.raises(BadStructure) as exc_info:
            simple_exporter.validate()
        assert "does not have original" in str(exc_info.value)

    @pytest.mark.parametrize("template_type", [CheckerExportConfig.TemplateType.CREATE, CheckerExportConfig.TemplateType.SEARCH])
    def test_simple_validate_wrong_template_type(self, tmpdir: Path, simple_exporter: Exporter, template_type: str) -> None:
        simple_exporter.export_config.templates = template_type

        with pytest.raises(BadStructure) as exc_info:
            simple_exporter.validate()
        assert "Templating set to" in str(exc_info.value)

    @pytest.mark.parametrize(
        "file_content", [
            "TEM!PLATE START\nHello\nTEMPLATE END\n",
            "TEMPLATE START\nHello\nTEMPL!ATE END\n",
            "Hello\n",
            "TEMPLATE START\nHello\nTEMPLATE END\nTEMPLATE START\nHello\nTEMP!LATE END\n",
            "TEMPLATE START\nHello\nTEMPLATE END\n\nHello\nTEMPLATE END\n",
            "TEMPLATE START\nHello\nTEMPLATE END\nTEMPLATE START\nHello\n",
            "TEMPLATE START\nTEMPLATE START\nHello\nTEMPLATE END\nTEMPLATE END",
        ]
    )
    def test_simple_validate_wrong_template_comment(self, tmpdir: Path, simple_exporter: Exporter, file_content: str) -> None:
        simple_exporter.export_config.templates = CheckerExportConfig.TemplateType.CREATE

        # remove .template and write comment-style template
        Path(tmpdir / "repository" / "task2" / "test.txt.template").unlink()
        (tmpdir / "repository" / "task2" / "test.txt").write_text(file_content, encoding="utf-8")

        with pytest.raises(BadStructure) as exc_info:
            simple_exporter.validate()
        assert "invalid template comments" in str(exc_info.value) or "does not have template comments" in str(exc_info.value)

    # TODO: ignore_templates tests
    @pytest.mark.parametrize(
        "file_structure, expected_excluded_paths",
        [
            (
                {},
                [],
            ),
            (
                {"some_folder": {"some_file.txt": "123", "empty_file.py": ""}, "other_file": "123"},
                [],
            ),
            (
                {"some_folder": {"some_file.txt": "123", "not_in_the_root_folder.py": "TEMPLATE START\nTEMPLATE END"}, "other_file": "123"},
                [],  # search in current dir only
            ),
            (
                {"some_folder": {"some_file.txt": "123"}, "empty_after_template_file.py": "TEMPLATE START\nTEMPLATE END"},
                ["empty_after_template_file.py"],
            ),
            (
                {"some_folder": {"some_file.txt": "123"}, "empty_after_template_file.py": "   \n\n  TEMPLATE START\n\nTEMPLATE END\n\t\n"},
                ["empty_after_template_file.py"]
            ),
            (
                {"some_folder": {"some_file.txt.template": "123", "some_file.txt": "321", "empty_file.py": ""}, "other_file": "123"},
                [],  # search in current dir only
            ),
            (
                {"some_folder": {"empty_file.py": ""}, "some_file.txt.template": "123", "some_file.txt": "321"},
                ["some_file.txt"],
            ),
            (
                {"some_folder.template": {"some_file.txt": "123", "empty_file.py": ""}, "some_folder": {"some_file": ""}, "other_file": "123"},
                ["some_folder"],
            ),
            (
                {"some_folder": {"some_file.txt.template": "123", "some_file.txt": "321", "empty_file.py": ""}, "other_file": "TEMPLATE START\nTEMPLATE END", "other_other_file": "", "other_other_file.template": ""},
                ["other_other_file", "other_file"],
            ),
        ],
    )
    def test_search_for_exclude_due_to_templates(self, tmpdir: Path, simple_exporter: Exporter, generate_file_structure: T_GENERATE_FILE_STRUCTURE, file_structure: dict[str, Any], expected_excluded_paths: list[str]) -> None:
        # use other directory, not original Exporter one
        generate_file_structure(file_structure, root=Path(tmpdir / "test_data"))

        excluded_paths = simple_exporter._search_for_exclude_due_to_templates(Path(tmpdir / "test_data"), False)
        assert sorted(excluded_paths) == sorted(expected_excluded_paths)

    @pytest.mark.parametrize(
        "copy_public, copy_private, copy_other, expected_files",
        [
            (True, False, False, ["task1/public_file.py", "public_file.py", "public_folder/file_in_public_folder"]),
            (False, True, False, ["task1/.task.yml", "task2/.task.yml", "task2/.private.file", ".private.file"]),
            (False, False, True, ["task1/test.txt", "task2/test.txt", "just_file"]),
        ]
    )
    @pytest.mark.parametrize(
        "fill_templates", [True, False],
    )
    def test_copy_files_with_config(self, tmpdir: Path, simple_exporter: Exporter, copy_public: bool, copy_private: bool, copy_other: bool, expected_files: list[str], fill_templates: bool) -> None:
        source = Path(tmpdir / "repository")
        destination = Path(tmpdir / "export")

        simple_exporter._copy_files_with_config(
            source, destination, simple_exporter.structure_config, copy_public, copy_private, copy_other, fill_templates
        )

        assert_files_in_folder(destination, expected_files)

    @pytest.mark.parametrize("is_file", [True, False])
    def test_copy_files_with_config_empty_template(self, tmpdir: Path, simple_exporter: Exporter, is_file: bool) -> None:
        # set .template as empty file/folder will delete original file
        if is_file:
            Path(tmpdir / "repository" / "task2" / "test.txt.template").write_text("", encoding="utf-8")
        else:
            Path(tmpdir / "repository" / "task2" / "test.txt.template").unlink()
            Path(tmpdir / "repository" / "task2" / "test.txt.template").mkdir()

        simple_exporter._copy_files_with_config(
            Path(tmpdir / "repository"), Path(tmpdir / "export"), simple_exporter.structure_config, False, False, True, True,
        )

        assert_files_in_folder(Path(tmpdir / "export"), ["task1/test.txt", "just_file"])

    @pytest.mark.parametrize("is_source_file", [True, False])
    @pytest.mark.parametrize("is_destination_file", [True, False])
    def test_copy_files_with_config_template_is_file_or_folder(self, tmpdir: Path, simple_exporter: Exporter, is_source_file: bool, is_destination_file: bool) -> None:
        repository = Path(tmpdir / "repository")
        export = Path(tmpdir / "export")

        # delete original template
        Path(repository / "task2" / "test.txt").unlink()
        Path(repository / "task2" / "test.txt.template").unlink()

        # make template folder or file
        if is_source_file:
            Path(repository / "task2" / "test.txt.template").write_text("NEW TEXT", encoding="utf-8")
        else:
            Path(repository / "task2" / "test.txt.template").mkdir()
            Path(repository / "task2" / "test.txt.template" / "new_file.txt").write_text("NEW TEXT", encoding="utf-8")

        # make original folder or file
        if is_destination_file:
            Path(repository / "task2" / "test.txt").write_text("OLD TEXT", encoding="utf-8")
        else:
            Path(repository / "task2" / "test.txt").mkdir()
            Path(repository / "task2" / "test.txt" / "old_file.txt").write_text("OLD TEXT", encoding="utf-8")

        simple_exporter._copy_files_with_config(
            repository, export, simple_exporter.structure_config, False, False, True, True,
        )

        # regardless of original file - just copy there template
        if is_source_file:
            assert (export / "task2" / "test.txt").is_file()
            assert (export / "task2" / "test.txt").read_text(encoding="utf-8") == "NEW TEXT"
        else:
            assert (export / "task2" / "test.txt").is_dir()
            assert (export / "task2" / "test.txt" / "new_file.txt").is_file()
            assert (export / "task2" / "test.txt" / "new_file.txt").read_text(encoding="utf-8") == "NEW TEXT"

    def test_export_public(self, tmpdir: Path, simple_exporter: Exporter) -> None:
        simple_exporter.export_public(Path(tmpdir / "export"))

        assert_files_in_folder(
            Path(tmpdir / "export").resolve(),
            [
                "task1/test.txt",
                "task1/public_file.py",
                "task2/test.txt",
                "just_file",
                "public_folder/file_in_public_folder",
                "public_file.py",
            ],
        )
        # check templates was resolved if needed (all here)
        assert (tmpdir / "export" / "task1" / "test.txt").read_text(encoding="utf-8") == "Some TODO: Your code\n"
        assert (tmpdir / "export" / "task2" / "test.txt").read_text(encoding="utf-8") == "Will replace the file"

    def test_export_for_testing(self, tmpdir: Path, simple_exporter: Exporter) -> None:
        simple_exporter.export_for_testing(Path(tmpdir / "export"))

        assert_files_in_folder(
            Path(tmpdir / "export").resolve(),
            [
                "task1/.task.yml",
                "task1/test.txt",
                "task1/public_file.py",
                "task2/.task.yml",
                "task2/test.txt",
                "task2/.private.file",
                ".private.file",
                "just_file",
                "public_folder/file_in_public_folder",
                "public_file.py",
            ],
        )
        # check templates was resolved if needed (non here)
        assert (tmpdir / "export" / "task1" / "test.txt").read_text(encoding="utf-8") == "Some Changes"
        assert (tmpdir / "export" / "task2" / "test.txt").read_text(encoding="utf-8") == "Student changed it"
        assert (tmpdir / "export" / "just_file").read_text(encoding="utf-8") == "hey"
        # overwritten to public tests
        assert (tmpdir / "export" / "public_folder" / "file_in_public_folder").read_text(encoding="utf-8") == "file"
        assert (tmpdir / "export" / "task1" / "public_file.py").read_text(encoding="utf-8") == "print('Hello')\n"

    def test_export_for_contribution(self, tmpdir: Path, simple_exporter: Exporter) -> None:
        simple_exporter.export_for_contribution(Path(tmpdir / "export"))

        assert_files_in_folder(
            Path(tmpdir / "export").resolve(),
            [
                "task1/.task.yml",
                "task1/test.txt",
                "task1/public_file.py",
                "task2/.task.yml",
                "task2/test.txt",
                "task2/.private.file",
                ".private.file",
                "just_file",
                "public_folder/file_in_public_folder",
                "public_file.py",
            ],
        )
        # check templates was resolved if needed (non here)
        assert (tmpdir / "export" / "task1" / "test.txt").read_text(encoding="utf-8") == "Some TEMPLATE START\nHello\nTEMPLATE END\n"
        assert (tmpdir / "export" / "task2" / "test.txt").read_text(encoding="utf-8") == "Some"
        assert (tmpdir / "export" / "public_folder" / "file_in_public_folder").read_text(encoding="utf-8") == "try to change"
        assert (tmpdir / "export" / "task1" / "public_file.py").read_text(encoding="utf-8") == "print('Hello LOL this too')\n"


class _TestExporter:
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
    SAMPLE_EXPORT_CONFIG = CheckerExportConfig(
        destination="https://example.com",
        templates="search_or_create",
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
                "test.txt": "TEMPLATE START\nHello\nTEMPLATE END\n",
                ".test.py": "print('Hello')\n",  # not private anymore, override
            },
            "task2": {
                "junk_group_folder": {"some_junk_file.txt": "Junk\n"},
                "junk_group_folder.template": "",  # will delete junk_group_folder
                ".task.yml": "version: 1",
                "private.txt": "Private\n",
                "private.py": "print('Private')\n",
                "valid.txt": "Valid\n",
                "valid.txt.template": "Valid Template\n",
            },
            "junk_file.py": "123",
            ".group.yml": "version: 1\nstructure:\n    ignore_patterns: [junk_group_folder, junk_file.py]\n",
        },
        "root_task_1": {
            ".task.yml": "version: 1\nstructure:\n    public_patterns: []\n",
            ".private_exception": "Some line\n",  # not public anymore, override
            "test.txt": "Hello\n",
            "test.txt.template": "Hello Template\n",
        },
        "test.py": "print('Hello')\n",
        "test.txt": "Hello\n",
        ".some_file": "Some line\n",
        ".private_exception": "Some line\n",
        "private.txt": "Private\n",
        "private.py": "print('Private')\n",
    }

    def test_validate_ok_simple(
        self, tmpdir: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE
    ) -> None:
        structure_config = CheckerStructureConfig(
            ignore_patterns=[".gitignore"],
            private_patterns=[".*"],
            public_patterns=["*"],
        )
        generate_file_structure(
            {
                "task1": {".task.yml": "version: 1\n", "test.txt": "TEMPLATE START\nHello\nTEMPLATE END\n"},
                "test.py": "print('Hello')\n",
            },
            root=Path(tmpdir / "repository"),
        )
        course = Course(
            deadlines=DeadlinesConfig(
                version=1,
                settings={"timezone": "Europe/Berlin"},
                schedule=[
                    {
                        "group": "no_folder_group",
                        "enabled": True,
                        "start": "2021-01-01 00:00:00",
                        "tasks": [
                            {"task": "task1", "score": 1},
                        ],
                    },
                ],
            ),
            repository_root=Path(tmpdir / "repository"),
        )
        exporter = Exporter(
            course,
            structure_config,
            self.SAMPLE_EXPORT_CONFIG,
            Path(tmpdir / "repository"),
        )
        exporter.validate()


    def test_search_for_exclude_due_templates(
            self,
            tmpdir: Path,
            generate_file_structure: T_GENERATE_FILE_STRUCTURE,
            file_structure: dict[str, Any],
            expected_excluded_paths: list[str],
    ) -> None:
        generate_file_structure(self.SAMPLE_TEST_FILES, root=Path(tmpdir / "repository"))
        course = Course(
            deadlines=self.SAMPLE_TEST_DEADLINES_CONFIG,
            repository_root=Path(tmpdir / "repository"),
        )
        exporter = Exporter(
            course,
            self.SAMPLE_TEST_STRUCTURE_CONFIG,
            self.SAMPLE_EXPORT_CONFIG,
            Path(tmpdir / "repository"),
        )

        generate_file_structure(file_structure, root=Path(tmpdir / "test_data"))
        excluded_paths = exporter._search_for_exclude_due_to_templates(Path(tmpdir / "test_data"), False)
        assert sorted(path_name for path_name in excluded_paths) == sorted(expected_excluded_paths)

    @pytest.mark.parametrize(
        "file_content", [
            "TEM!PLATE START\nHello\nTEMPLATE END\n",
            "TEMPLATE START\nHello\nTEMPL!ATE END\n",
            "Hello\n",
            "TEMPLATE START\nHello\nTEMPLATE END\nTEMPLATE START\nHello\nTEMP!LATE END\n",
            "TEMPLATE START\nHello\nTEMPLATE END\n\nHello\nTEMPLATE END\n",
            "TEMPLATE START\nHello\nTEMPLATE END\nTEMPLATE START\nHello\n",
            "TEMPLATE START\nTEMPLATE START\nHello\nTEMPLATE END\nTEMPLATE END",
        ]
    )
    def test_validate_template_wrong_template_comments(
        self, tmpdir: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE, file_content: str,
    ) -> None:
        structure_config = CheckerStructureConfig(
            ignore_patterns=[".gitignore"],
            private_patterns=[".*"],
            public_patterns=["*"],
        )
        generate_file_structure(
            {
                "task1": {".task.yml": "version: 1\n", "test.txt": file_content},
                "test.py": "print('Hello')\n",
            },
            root=Path(tmpdir / "repository"),
        )
        course = Course(
            deadlines=DeadlinesConfig(
                version=1,
                settings={"timezone": "Europe/Berlin"},
                schedule=[
                    {
                        "group": "no_folder_group",
                        "enabled": True,
                        "start": "2021-01-01 00:00:00",
                        "tasks": [
                            {"task": "task1", "score": 1},
                        ],
                    },
                ],
            ),
            repository_root=Path(tmpdir / "repository"),
        )
        exporter = Exporter(
            course,
            structure_config,
            CheckerExportConfig(destination="https://example.com", templates="create"),
            Path(tmpdir / "repository"),
        )
        with pytest.raises(BadStructure):
            exporter.validate()

    def test_validate_template_search_ok(self, tmpdir: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE) -> None:
        structure_config = CheckerStructureConfig(
            ignore_patterns=[".gitignore"],
            private_patterns=[".*"],
            public_patterns=["*"],
        )
        generate_file_structure(
            {
                "folder": {"test.txt.template": "Hello\n"},
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
            self.SAMPLE_EXPORT_CONFIG,
            Path(tmpdir / "repository"),
        )

        exporter.validate()

    def test_export_public(self, tmpdir: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE) -> None:
        generate_file_structure(self.SAMPLE_TEST_FILES, root=Path(tmpdir / "repository"))
        course = Course(
            deadlines=self.SAMPLE_TEST_DEADLINES_CONFIG,
            repository_root=Path(tmpdir / "repository"),
        )
        exporter = Exporter(
            course,
            self.SAMPLE_TEST_STRUCTURE_CONFIG,
            self.SAMPLE_EXPORT_CONFIG,
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
            self.SAMPLE_EXPORT_CONFIG,
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
            self.SAMPLE_EXPORT_CONFIG,
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
