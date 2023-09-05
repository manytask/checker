import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Type

import pytest

from checker.exceptions import TaskTesterTestConfigException, TesterNotImplemented
from checker.testers.cpp import CppTester
from checker.testers.make import MakeTester
from checker.testers.python import PythonTester
from checker.testers.tester import Tester


class TestTester:
    @pytest.mark.parametrize('tester_name,tester_class', [
        ('python', PythonTester),
        ('cpp', CppTester),
        ('make', MakeTester),
    ])
    def test_right_tester_created(self, tester_name: str, tester_class: Type[Tester]) -> None:
        tester = Tester.create(tester_name)
        assert isinstance(tester, tester_class)

    def test_wrong_tester(self) -> None:
        with pytest.raises(TesterNotImplemented):
            Tester.create('definitely-wrong-tester')


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
