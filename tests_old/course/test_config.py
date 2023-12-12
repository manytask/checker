from __future__ import annotations

from pathlib import Path

import pytest

from checker_old.course.config import CourseConfig
from checker_old.exceptions import BadConfig


DATA_FOLDER = Path(__file__).parents[1] / 'data' / 'config'


class TestConfig:
    def test_(self) -> None:
        pass

    def test_wrong_file(self, tmp_path: Path) -> None:
        with pytest.raises(BadConfig):
            CourseConfig.from_yaml(DATA_FOLDER / 'not-existed-file.yml')

        with pytest.raises(BadConfig):
            CourseConfig.from_yaml(DATA_FOLDER / 'bad-config.yml')

        tmp_file = tmp_path / 'empty-file.yml'
        tmp_file.touch()
        with pytest.raises(BadConfig):
            CourseConfig.from_yaml(tmp_file)
