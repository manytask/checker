from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from checker.course.schedule import CourseSchedule, Group, Task
from checker.exceptions import BadConfig


DATA_FOLDER = Path(__file__).parents[1] / 'data' / 'schedule'


class TestTask:
    @pytest.fixture(scope='function')
    def sample_group(self) -> Group:
        return Group(
            name='test_group',
            start=datetime(2000, 1, 1),
            deadline=datetime(2050, 1, 1),
            second_deadline=datetime(2100, 1, 1),
        )

    @pytest.mark.parametrize('reserved_name', [
        'task', 'test', 'solution', 'template',
    ])
    def test_reserved_task_name(self, sample_group: Group, reserved_name: str) -> None:
        with pytest.raises(AssertionError, match=f'.*{reserved_name}.*reserved.*'):
            Task(
                group=sample_group,
                name=reserved_name,
                max_score=10,
            )


class TestGroup:
    def test_basics(self) -> None:
        group_minimal = Group(
            name='test_group',
            start=datetime(2000, 1, 1),
            deadline=datetime(2002, 1, 1),
            second_deadline=datetime(2004, 1, 1),
        )

        assert group_minimal.is_enabled
        # TODO: mock and test ended started ect

        group_max = Group(
            name='test_group',
            start=datetime(2000, 1, 1),
            deadline=datetime(2002, 1, 1),
            second_deadline=datetime(2004, 1, 1),
            enabled=True,
            marked=True,
        )

        assert group_max.is_enabled
        # TODO: mock and test ended started ect

    @pytest.mark.parametrize('deadline,second_deadline,submit_time,extra_time,percentage', [
        (datetime(2020, 1, 1), datetime(2024, 1, 1), datetime(2024, 1, 1), None, 0),
        (datetime(2020, 1, 1), datetime(2024, 1, 1), datetime(2026, 1, 1), None, 0),
        (datetime(2020, 1, 1), datetime(2024, 1, 1), datetime(2020, 1, 1), None, 1),
        (datetime(2020, 1, 1), datetime(2024, 1, 1), datetime(2018, 1, 1), None, 1),
        (datetime(2020, 1, 1), datetime(2024, 1, 1), datetime(2022, 1, 1), None, 0.5),
        (datetime(2020, 1, 1), datetime(2024, 1, 1), datetime(2021, 1, 1), None, 0.75),
        (datetime(2020, 1, 1), datetime(2024, 1, 1), datetime(2023, 1, 1), None, 0.25),
        (datetime(2020, 1, 1), datetime(2024, 1, 1), datetime(2021, 1, 1), timedelta(days=365), 1),
        (datetime(2020, 1, 1), datetime(2024, 1, 1), datetime(2024, 1, 1), timedelta(days=2*365), 0.5),
    ])
    def test_get_deadline_percentage(
            self,
            deadline: datetime,
            second_deadline: datetime,
            submit_time: datetime,
            extra_time: timedelta | None,
            percentage: float,
    ) -> None:
        group = Group(
            name='test_group',
            start=datetime(2000, 1, 1),
            deadline=deadline,
            second_deadline=second_deadline,
        )
        assert group.get_deadline_percentage(submit_time, extra_time) == pytest.approx(percentage, 0.01)

    def test_get_is_overdue(self) -> None:
        group = Group(
            name='test_group',
            start=datetime(2000, 1, 1),
            deadline=datetime(2002, 1, 1),
            second_deadline=datetime(2004, 1, 1),
        )

        assert not group.get_is_overdue_first(datetime(2001, 1, 1))
        assert group.get_is_overdue_first(datetime(2003, 1, 1))
        assert group.get_is_overdue_first(datetime(2005, 1, 1))

        assert not group.get_is_overdue_second(datetime(2003, 1, 1))
        assert group.get_is_overdue_second(datetime(2005, 1, 1))


class TestSchedule:
    def test_wrong_file(self, tmp_path: Path) -> None:
        with pytest.raises(BadConfig):
            CourseSchedule(DATA_FOLDER / 'not-existed-file.yml')

        with pytest.raises(BadConfig):
            CourseSchedule(DATA_FOLDER / 'bad-config.yml')

        tmp_file = tmp_path / 'empty-file.yml'
        tmp_file.touch()
        with pytest.raises(BadConfig):
            CourseSchedule(tmp_file)

    def test_get_tasks(self) -> None:
        pass

    def test_get_groups(self) -> None:
        pass
