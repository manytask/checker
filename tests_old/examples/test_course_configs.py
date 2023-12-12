from __future__ import annotations

from pathlib import Path

from checker_old.course.config import CourseConfig
from checker_old.course.schedule import CourseSchedule


EXAMPLES_FOLDER = Path(__file__).parents[2] / 'examples'


class TestCourse:
    def test_read_course(self) -> None:
        CourseConfig.from_yaml(EXAMPLES_FOLDER / '.course.yml')


class TestDeadlines:
    def test_read_course(self) -> None:
        CourseSchedule(EXAMPLES_FOLDER / '.deadlines.yml')
