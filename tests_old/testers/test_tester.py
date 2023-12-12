from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Type

import pytest

from checker_old.exceptions import TaskTesterTestConfigException, TesterNotImplemented
from checker_old.testers.cpp import CppTester
from checker_old.testers.make import MakeTester
from checker_old.testers.python import PythonTester
from checker_old.testers.tester import Tester
from checker_old.course import CourseConfig


def create_test_course_config(**kwargs) -> CourseConfig:
    return CourseConfig(
        name='test',
        deadlines='',
        templates='',
        manytask_url='',
        course_group='',
        public_repo='',
        students_group='',
        **kwargs,
    )

def write_tester_to_file(path: Path, content: str) -> Path:
    filename = path / 'tester.py'
    content = inspect.cleandoc(content)
    with open(filename, 'w') as f:
        f.write(content)
    return filename


class TestTester:
    @pytest.mark.parametrize('tester_name,tester_class', [
        ('python', PythonTester),
        ('cpp', CppTester),
        ('make', MakeTester),
    ])
    def test_right_tester_created(self, tester_name: str, tester_class: Type[Tester]) -> None:
        course_config = create_test_course_config(system=tester_name)
        tester = Tester.create(root=Path(), course_config=course_config)
        assert isinstance(tester, tester_class)

    def test_external_tester(self, tmp_path: Path):
        TESTER = """
        from checker_old.testers import Tester
        class CustomTester(Tester):
            definitely_external_tester = 'Yes!'
        """
        course_config = create_test_course_config(system='external', tester_path='tester.py')
        write_tester_to_file(tmp_path, TESTER)
        tester = Tester.create(root=tmp_path, course_config=course_config)
        assert hasattr(tester, 'definitely_external_tester')

    NOT_A_TESTER = """
        class NotATester:
            definitely_external_tester = 'Yes!'
        """

    NOT_INHERITED_TESTER = """
        class CustomTester:
            definitely_external_tester = 'Yes!'
        """

    @pytest.mark.parametrize('tester_content', [
        NOT_A_TESTER,
        NOT_INHERITED_TESTER,
    ])
    def test_invalid_external_tester(self, tmp_path: Path, tester_content):
        course_config = create_test_course_config(system='external', tester_path='tester.py')
        write_tester_to_file(tmp_path, tester_content)
        with pytest.raises(TesterNotImplemented):
            Tester.create(root=tmp_path, course_config=course_config)

    def test_wrong_tester(self) -> None:
        course_config = create_test_course_config(system='definitely-wrong-tester')
        with pytest.raises(TesterNotImplemented):
            Tester.create(root=Path(), course_config=course_config)


@dataclass
class SampleTaskTestConfig(Tester.TaskTestConfig):
    digit: int = 0
    flag: bool = True
    string: str = 'string'


def write_config_to_file(path: Path, content: str) -> Path:
    filename = path / '.tester.json'
    content = inspect.cleandoc(content)
    with open(filename, 'w') as f:
        f.write(content)
    return filename


class TestTaskTestConfig:
    def test_read_json_empty_file(self, tmp_path: Path) -> None:
        CONFIG = """
        """
        filename = write_config_to_file(tmp_path, CONFIG)
        with pytest.raises(TaskTesterTestConfigException):
            SampleTaskTestConfig.from_json(filename)

    def test_read_json_wrong_layout(self, tmp_path: Path) -> None:
        CONFIG = """
        "a": 1
        """
        filename = write_config_to_file(tmp_path, CONFIG)
        with pytest.raises(TaskTesterTestConfigException):
            SampleTaskTestConfig.from_json(filename)

    def test_read_json_wrong_format(self, tmp_path: Path) -> None:
        CONFIG = """
        a: 1
        """
        filename = write_config_to_file(tmp_path, CONFIG)
        with pytest.raises(TaskTesterTestConfigException):
            SampleTaskTestConfig.from_json(filename)

    def test_read_json_extra_fields(self, tmp_path: Path) -> None:
        CONFIG = """
        {"a": "a"}
        """
        filename = write_config_to_file(tmp_path, CONFIG)
        with pytest.raises(TaskTesterTestConfigException):
            SampleTaskTestConfig.from_json(filename)

    def test_simple_case_empty_json(self, tmp_path: Path) -> None:
        CONFIG = '{}'
        filename = write_config_to_file(tmp_path, CONFIG)

        config = SampleTaskTestConfig.from_json(filename)
        assert config.digit == 0
        assert config.flag
        assert config.string == 'string'

    def test_simple_case_read_json(self, tmp_path: Path) -> None:
        CONFIG = """
        {
            "digit": 1,
            "flag": false,
            "string": "hard"
        }
        """
        filename = write_config_to_file(tmp_path, CONFIG)

        config = SampleTaskTestConfig.from_json(filename)
        assert config.digit == 1
        assert not config.flag
        assert config.string == 'hard'
