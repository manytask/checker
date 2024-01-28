from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import Any

import pytest


if sys.version_info < (3, 8):
    from pytz import timezone as ZoneInfo
else:
    from zoneinfo import ZoneInfo

from pydantic import ValidationError

from checker.configs.manytask import ManytaskDeadlinesConfig


class TestManytaskDeadlinesConfig:
    def test_minimal_init(self) -> None:
        ManytaskDeadlinesConfig(
            timezone="Europe/Moscow",
            schedule=[],
        )
        assert True

    def test_maximal_init(self) -> None:
        ManytaskDeadlinesConfig(
            timezone="Europe/Moscow",
            deadlines="hard",
            max_submissions=10,
            submission_penalty=0.1,
            schedule=[
                {
                    "group": "group1",
                    "start": "2021-01-01 00:00",
                    "end": "2021-01-01 00:00",
                    "tasks": [
                        {
                            "task": "task1",
                            "score": 10,
                        },
                    ],
                },
            ],
        )
        assert True

    @pytest.mark.parametrize(
        "timezone",
        [
            "Europe/Moscow1",
            "Asia/Moscow",
            "US",
            "Europe",
            "Europe/Moscow/Moscow",
        ],
    )
    def test_invalid_timezone(self, timezone: str) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone=timezone,
                schedule=[],
            )

    @pytest.mark.parametrize(
        "timezone",
        [
            "CET",
            "UTC",
            "Europe/Moscow",
            "Europe/Kiev",
            "Europe/London",
            "Europe/Paris",
            "Europe/Berlin",
            "Europe/Rome",
        ],
    )
    def test_valid_timezone(self, timezone: str) -> None:
        real_timezone = ZoneInfo(timezone)
        real_start = datetime.strptime("2021-01-01 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=real_timezone)
        real_step = real_start + timedelta(days=1)
        real_end = real_start + timedelta(days=2)

        # check all deadlines have timezone set
        deadlines = ManytaskDeadlinesConfig(
            timezone=timezone,
            schedule=[
                {
                    "group": "group1",
                    "start": real_start.strftime("%Y-%m-%d %H:%M"),
                    "steps": {
                        0.5: real_step.strftime("%Y-%m-%d %H:%M"),
                    },
                    "end": real_end.strftime("%Y-%m-%d %H:%M"),
                    "tasks": [
                        {
                            "task": "task1",
                            "score": 10,
                        },
                    ],
                },
            ],
        )

        assert deadlines.timezone == timezone

        for group in deadlines.get_groups():
            assert group.start.tzinfo == real_timezone
            assert group.start.time() == real_start.time()
            for _, date in group.steps.items():
                if isinstance(date, datetime):
                    assert date.tzinfo == real_timezone
                    assert date.time() == real_step.time()
            if isinstance(group.end, datetime):
                assert group.end.tzinfo == real_timezone
                assert group.end.time() == real_end.time()

    def test_invalid_deadlines(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone="Europe/Moscow",
                deadlines="hard1",
                schedule=[],
            )

    @pytest.mark.parametrize(
        "max_submissions",
        [-1, 0, 1.2],
    )
    def test_invalid_max_submissions(self, max_submissions: Any) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone="Europe/Moscow",
                max_submissions=max_submissions,
                schedule=[],
            )

    @pytest.mark.parametrize(
        "submission_penalty",
        [-1, -0.2],
    )
    def test_invalid_submission_penalty(self, submission_penalty: Any) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone="Europe/Moscow",
                submission_penalty=submission_penalty,
                schedule=[],
            )

    def test_group_names_not_unique(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone="Europe/Moscow",
                schedule=[
                    {
                        "group": "group1",
                        "start": "2021-01-01 00:00",
                        "end": "2021-01-01 00:00",
                        "tasks": [],
                    },
                    {
                        "group": "group1",
                        "start": "2021-01-01 00:00",
                        "end": "2021-01-01 00:00",
                        "tasks": [],
                    },
                ],
            )

    def test_task_names_not_unique(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone="Europe/Moscow",
                schedule=[
                    {
                        "group": "group1",
                        "start": "2021-01-01 00:00",
                        "end": "2021-01-01 00:00",
                        "tasks": [
                            {
                                "task": "task1",
                                "score": 10,
                            },
                            {
                                "task": "task2",
                                "score": 10,
                            },
                        ],
                    },
                    {
                        "group": "group2",
                        "start": "2021-01-01 00:00",
                        "end": "2021-01-01 00:00",
                        "tasks": [
                            {
                                "task": "task1",
                                "score": 10,
                            },
                        ],
                    },
                ],
            )

    def test_group_name_same_as_task_name(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone="Europe/Moscow",
                schedule=[
                    {
                        "group": "group1",
                        "start": "2021-01-01 00:00",
                        "end": "2021-01-01 00:00",
                        "tasks": [
                            {
                                "task": "task1",
                                "score": 10,
                            },
                        ],
                    },
                    {
                        "group": "task1",
                        "start": "2021-01-01 00:00",
                        "end": "2021-01-01 00:00",
                        "tasks": [
                            {
                                "task": "task2",
                                "score": 10,
                            },
                        ],
                    },
                ],
            )

    @pytest.mark.parametrize(
        "enabled, started, now, expected_tasks, expected_groups",
        [
            (None, None, None, ["task1_1", "task1_2", "task2_1", "task2_2", "task3_1"], ["group1", "group2", "group3"]),
            (True, None, None, ["task1_1", "task3_1"], ["group1", "group3"]),
            (False, None, None, ["task1_2", "task2_1", "task2_2"], ["group2"]),
            (None, True, None, ["task1_1", "task1_2", "task2_1", "task2_2"], ["group1", "group2"]),
            (None, False, None, ["task3_1"], ["group3"]),
            (True, True, None, ["task1_1"], ["group1"]),
            (True, False, None, ["task3_1"], ["group3"]),
            (None, True, datetime(2021, 1, 1), ["task1_1", "task1_2"], ["group1"]),
            (None, False, datetime(2021, 1, 1), ["task2_1", "task2_2", "task3_1"], ["group2", "group3"]),
        ],
    )
    def test_get_tasks_groups(
        self,
        enabled: bool | None,
        started: bool | None,
        now: datetime | None,
        expected_tasks: list[str],
        expected_groups: list[str],
    ) -> None:
        timezone = ZoneInfo("Europe/Moscow")
        if now is not None:
            now = now.replace(tzinfo=timezone)

        deadlines = ManytaskDeadlinesConfig(
            timezone="Europe/Moscow",
            schedule=[
                {
                    "group": "group1",
                    "start": "2020-01-01 00:00",
                    "end": "2020-05-01 00:00",
                    "tasks": [
                        {
                            "task": "task1_1",
                            "score": 10,
                        },
                        {
                            "task": "task1_2",
                            "enabled": False,
                            "score": 10,
                        },
                    ],
                },
                {
                    "group": "group2",
                    "start": "2022-01-01 00:00",
                    "end": "2022-05-01 00:00",
                    "enabled": False,
                    "tasks": [
                        {
                            "task": "task2_1",
                            "score": 10,
                        },
                        {
                            "task": "task2_2",
                            "score": 10,
                        },
                    ],
                },
                {
                    "group": "group3",
                    "start": "3000-01-01 00:00",
                    "end": "3000-05-01 00:00",
                    "tasks": [
                        {
                            "task": "task3_1",
                            "score": 10,
                        },
                    ],
                },
            ],
        )

        groups = deadlines.get_groups(enabled=enabled, started=started, now=now)
        tasks = deadlines.get_tasks(enabled=enabled, started=started, now=now)

        assert len([i.name for i in groups]) == len(expected_groups), "Number of groups is not correct"
        assert len([i.name for i in tasks]) == len(expected_tasks), "Number of tasks is not correct"
