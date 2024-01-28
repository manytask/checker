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


class ManytaskSettingsConfig(CustomBaseModel):
    """Manytask settings."""

    course_name: str
    gitlab_base_url: AnyUrl
    public_repo: str
    students_group: str


class ManytaskUiConfig(CustomBaseModel):
    task_url_template: str  # $GROUP_NAME $TASK_NAME vars are available
    links: Optional[dict[str, str]] = None  # pedantic 3.9 require Optional, not | None

    @field_validator("task_url_template")
    @classmethod
    def check_task_url_template(cls, data: str | None) -> str | None:
        if data is not None and (not data.startswith("http://") and not data.startswith("https://")):
            raise ValueError("task_url_template should be http or https")
        # if data is not None and "$GROUP_NAME" not in data and "$TASK_NAME" not in data:
        #     raise ValueError("task_url should contain at least one of $GROUP_NAME and $TASK_NAME vars")
        return data


class ManytaskDeadlinesType(Enum):
    HARD = "hard"
    INTERPOLATE = "interpolate"


class ManytaskTaskConfig(CustomBaseModel):
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


class ManytaskGroupConfig(CustomBaseModel):
    group: str

    enabled: bool = True

    # Note: use Optional/Union[...] instead of ... | None as pydantic does not support | in older python versions
    start: datetime
    steps: dict[float, Union[datetime, timedelta]] = Field(default_factory=dict)
    end: Union[datetime, timedelta, None] = None

    tasks: list[ManytaskTaskConfig] = Field(default_factory=list)

    @property
    def name(self) -> str:
        return self.group

    def replace_timezone(self, timezone: ZoneInfo) -> None:
        self.start = self.start.replace(tzinfo=timezone)
        self.end = self.end.replace(tzinfo=timezone) if isinstance(self.end, datetime) else self.end
        self.steps = {k: v.replace(tzinfo=timezone) for k, v in self.steps.items() if isinstance(v, datetime)}

    @model_validator(mode="after")
    def check_dates(self) -> "ManytaskGroupConfig":
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


class ManytaskDeadlinesConfig(CustomBaseModel):
    timezone: str

    # Note: use Optional/Union[...] instead of ... | None as pydantic does not support | in older python versions
    deadlines: ManytaskDeadlinesType = ManytaskDeadlinesType.HARD
    max_submissions: Optional[int] = None
    submission_penalty: float = 0

    schedule: list[ManytaskGroupConfig]  # list of groups with tasks

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

    @field_validator("schedule")
    @classmethod
    def check_group_names_unique(cls, data: list[ManytaskGroupConfig]) -> list[ManytaskGroupConfig]:
        groups = [group.name for group in data]
        duplicates = [name for name in groups if groups.count(name) > 1]
        if duplicates:
            raise ValueError(f"Group names should be unique, duplicates: {duplicates}")
        return data

    @field_validator("schedule")
    @classmethod
    def check_task_names_unique(cls, data: list[ManytaskGroupConfig]) -> list[ManytaskGroupConfig]:
        tasks_names = [task.name for group in data for task in group.tasks]
        duplicates = [name for name in tasks_names if tasks_names.count(name) > 1]
        if duplicates:
            raise ValueError(f"Task names should be unique, duplicates: {duplicates}")
        return data

    @model_validator(mode="after")
    def set_timezone(self) -> "ManytaskDeadlinesConfig":
        timezone = ZoneInfo(self.timezone)
        for group in self.schedule:
            group.replace_timezone(timezone)
        return self

    def get_groups(
        self,
        enabled: bool | None = None,
    ) -> list[ManytaskGroupConfig]:
        groups = [group for group in self.schedule]

        if enabled is not None:
            groups = [group for group in groups if group.enabled == enabled]

        # TODO: check time

        return groups

    def get_tasks(
        self,
        enabled: bool | None = None,
    ) -> list[ManytaskTaskConfig]:
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


class ManytaskConfig(CustomBaseModel, YamlLoaderMixin["ManytaskConfig"]):
    """Manytask configuration."""

    version: int  # if config exists, version is always present

    settings: ManytaskSettingsConfig
    ui: ManytaskUiConfig
    deadlines: ManytaskDeadlinesConfig

    def get_groups(
        self,
        enabled: bool | None = None,
    ) -> list[ManytaskGroupConfig]:
        return self.deadlines.get_groups(enabled=enabled)

    def get_tasks(
        self,
        enabled: bool | None = None,
    ) -> list[ManytaskTaskConfig]:
        return self.deadlines.get_tasks(enabled=enabled)

    @field_validator("version")
    @classmethod
    def check_version(cls, data: int) -> int:
        if data != 1:
            raise ValueError(f"Only version 1 is supported for {cls.__name__}")
        return data
