from __future__ import annotations

import sys
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Union


if sys.version_info < (3, 8):
    from pytz import ZoneInfoNotFoundError as ZoneInfoNotFoundError, timezone as ZoneInfo
else:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AnyUrl, Field, field_validator, model_validator

from .utils import CustomBaseModel, YamlLoaderMixin


class DeadlinesType(Enum):
    HARD = "hard"
    INTERPOLATE = "interpolate"


class DeadlinesSettingsConfig(CustomBaseModel):
    timezone: str

    # Note: use Optional/Union[...] instead of ... | None as pydantic does not support | in older python versions
    deadlines: DeadlinesType = DeadlinesType.HARD
    max_submissions: Optional[int] = None
    submission_penalty: float = 0

    task_url: Optional[AnyUrl] = None  # $GROUP_NAME $TASK_NAME vars are available

    @field_validator("task_url")
    @classmethod
    def check_task_url(cls, data: AnyUrl | None) -> AnyUrl | None:
        if data is not None and data.scheme not in ("http", "https"):
            raise ValueError("task_url should be http or https")
        return data

    @field_validator("max_submissions")
    @classmethod
    def check_max_submissions(cls, data: int | None) -> int | None:
        if data is not None and data <= 0:
            raise ValueError("max_submissions should be positive")
        return data

    @field_validator("timezone")
    @classmethod
    def check_valid_timezone(cls, timezone: str) -> str:
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as e:
            raise ValueError(str(e))
        return timezone


class DeadlinesTaskConfig(CustomBaseModel):
    task: str

    enabled: bool = True

    score: int
    bonus: int = 0
    special: int = 0

    # Note: use Optional/Union[...] instead of ... | None as pydantic does not support | in older python versions
    url: Optional[AnyUrl] = None

    @property
    def name(self) -> str:
        return self.task


class DeadlinesGroupConfig(CustomBaseModel):
    group: str

    enabled: bool = True

    # Note: use Optional/Union[...] instead of ... | None as pydantic does not support | in older python versions
    start: datetime
    steps: dict[float, Union[datetime, timedelta]] = Field(default_factory=dict)
    end: Union[datetime, timedelta, None] = None

    tasks: list[DeadlinesTaskConfig] = Field(default_factory=list)

    @property
    def name(self) -> str:
        return self.group

    @model_validator(mode="after")
    def check_dates(self) -> "DeadlinesGroupConfig":
        # check end
        if isinstance(self.end, timedelta) and self.end < timedelta():
            raise ValueError(f"end timedelta <{self.end}> should be positive")
        if isinstance(self.end, datetime) and self.end < self.start:
            raise ValueError(f"end datetime <{self.end}> should be after the start <{self.start}>")

        # check steps
        last_step_date_or_delta: datetime | timedelta = self.start
        for _, date_or_delta in self.steps.items():
            step_date = self.start + date_or_delta if isinstance(date_or_delta, timedelta) else date_or_delta
            last_step_date = (
                self.start + last_step_date_or_delta
                if isinstance(last_step_date_or_delta, timedelta)
                else last_step_date_or_delta
            )

            if isinstance(date_or_delta, timedelta) and date_or_delta < timedelta():
                raise ValueError(f"step timedelta <{date_or_delta}> should be positive")
            if isinstance(date_or_delta, datetime) and date_or_delta <= self.start:
                raise ValueError(f"step datetime <{date_or_delta}> should be after the start {self.start}")

            if step_date <= last_step_date:
                raise ValueError(
                    f"step datetime/timedelta <{date_or_delta}> "
                    f"should be after the last step <{last_step_date_or_delta}>"
                )
            last_step_date_or_delta = date_or_delta

        return self


class DeadlinesConfig(CustomBaseModel, YamlLoaderMixin["DeadlinesConfig"]):
    """Deadlines configuration."""

    version: int  # if config exists, version is always present

    settings: DeadlinesSettingsConfig
    schedule: list[DeadlinesGroupConfig]

    def get_groups(
        self,
        enabled: bool | None = None,
    ) -> list[DeadlinesGroupConfig]:
        groups = [group for group in self.schedule]

        if enabled is not None:
            groups = [group for group in groups if group.enabled == enabled]

        # TODO: check time

        return groups

    def get_tasks(
        self,
        enabled: bool | None = None,
    ) -> list[DeadlinesTaskConfig]:
        # TODO: refactor

        groups = self.get_groups()

        if enabled is True:
            groups = [group for group in groups if group.enabled]
            extra_tasks = []
        elif enabled is False:
            groups = groups
            extra_tasks = [task for group in groups for task in group.tasks if not group.enabled]
        else:  # None
            groups = groups
            extra_tasks = []

        tasks = [task for group in groups for task in group.tasks]

        if enabled is not None:
            tasks = [task for task in tasks if task.enabled == enabled]

        for extra_task in extra_tasks:
            if extra_task not in tasks:
                tasks.append(extra_task)

        # TODO: check time

        return tasks

    @field_validator("version")
    @classmethod
    def check_version(cls, data: int) -> int:
        if data != 1:
            raise ValueError(f"Only version 1 is supported for {cls.__name__}")
        return data

    @field_validator("schedule")
    @classmethod
    def check_group_names_unique(cls, data: list[DeadlinesGroupConfig]) -> list[DeadlinesGroupConfig]:
        groups = [group.name for group in data]
        duplicates = [name for name in groups if groups.count(name) > 1]
        if duplicates:
            raise ValueError(f"Group names should be unique, duplicates: {duplicates}")
        return data

    @field_validator("schedule")
    @classmethod
    def check_task_names_unique(cls, data: list[DeadlinesGroupConfig]) -> list[DeadlinesGroupConfig]:
        tasks_names = [task.name for group in data for task in group.tasks]
        duplicates = [name for name in tasks_names if tasks_names.count(name) > 1]
        if duplicates:
            raise ValueError(f"Task names should be unique, duplicates: {duplicates}")
        return data
