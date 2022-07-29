"""
Classes for Course, Groups and Tasks
They interact ONLY with deadlines, do not test anything, know nothing about physical folders
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from ..exceptions import BadConfig, BadGroupConfig, BadTaskConfig


@dataclass
class Task:
    group: 'Group'
    name: str
    full_name: str = field(init=False)

    max_score: int
    enabled: bool = True
    scoring_func: str = 'max'
    review: bool = False
    marked: bool = False

    def __post_init__(self) -> None:
        self.full_name = self.group.name + '/' + self.name

    @property
    def is_enabled(self) -> bool:
        return self.enabled and self.group.is_enabled

    @property
    def is_started(self) -> bool:
        return self.is_enabled and self.group.is_started

    @property
    def is_ended(self) -> bool:
        return self.is_enabled and self.group.is_ended

    def get_task_deadline_percentage(
            self,
            submit_time: datetime | None = None,
            extra_time: timedelta | None = None,
    ) -> float:
        return self.group.get_deadline_percentage(submit_time, extra_time)

    def get_is_overdue_first(
            self,
            submit_time: datetime | None = None,
            extra_time: timedelta | None = None,
    ) -> bool:
        return self.group.get_is_overdue_first(submit_time=submit_time, extra_time=extra_time)

    def get_is_overdue_second(
            self,
            submit_time: datetime | None = None,
            extra_time: timedelta | None = None,
    ) -> bool:
        return self.group.get_is_overdue_second(submit_time=submit_time, extra_time=extra_time)


@dataclass
class Group:
    name: str

    start: datetime
    deadline: datetime
    second_deadline: datetime

    enabled: bool = True
    marked: bool = False

    tasks: list[Task] = field(default_factory=list)

    @property
    def max_score(self) -> int:
        return sum([task.max_score for task in self.tasks])

    @property
    def is_enabled(self) -> bool:
        return self.enabled

    @property
    def is_started(self) -> bool:
        return self.is_enabled and self.start < datetime.now()  # TODO: check timezone

    @property
    def is_ended(self) -> bool:
        return self.is_enabled and self.second_deadline < datetime.now()  # TODO: check timezone

    def get_deadline_percentage(
            self,
            submit_time: datetime | None = None,
            extra_time: timedelta | None = None,
    ) -> float:
        extra_time = extra_time or timedelta()
        submit_time = submit_time or datetime.now()  # TODO: check timezone
        if self.second_deadline == self.deadline:
            return 1. if submit_time < self.second_deadline + extra_time else 0.

        deadlines_timedelta = self.second_deadline - self.deadline
        overdue_timedelta = self.second_deadline + extra_time - submit_time
        percentage = overdue_timedelta / deadlines_timedelta
        return max(0., min(percentage, 1.))

    def get_is_overdue_first(
            self,
            submit_time: datetime | None = None,
            extra_time: timedelta | None = None,
    ) -> bool:
        return self.get_deadline_percentage(submit_time, extra_time) < 1.

    def get_is_overdue_second(
            self,
            submit_time: datetime | None = None,
            extra_time: timedelta | None = None,
    ) -> bool:
        return self.get_deadline_percentage(submit_time, extra_time) == 0.


class CourseSchedule:
    def __init__(
            self,
            deadlines_config: Path,
    ):
        try:
            with open(deadlines_config) as config_file:
                deadlines = yaml.safe_load(config_file)
        except (yaml.YAMLError, FileNotFoundError) as e:
            raise BadConfig(f'Unable to load deadlines config file <{deadlines_config}>') from e

        if not deadlines:
            raise BadConfig(f'Empty config file <{deadlines_config}>')

        self.groups: OrderedDict[str, Group] = OrderedDict()
        self.tasks: OrderedDict[str, Task] = OrderedDict()

        for group_config in deadlines:
            group_name = None
            try:
                group_name = str(group_config.get('group'))
                group_enabled = bool(group_config.get('enabled', True))

                group_start = datetime.strptime(group_config.get('start'), '%d-%m-%Y %H:%M')
                group_deadline = datetime.strptime(group_config.get('deadline'), '%d-%m-%Y %H:%M')
                if second_deadline := group_config.get('second_deadline', None):
                    group_second_deadline = datetime.strptime(second_deadline, '%d-%m-%Y %H:%M')
                else:
                    group_second_deadline = group_deadline

                group_marked = bool(group_config.get('marked', False))
            except (KeyError, TypeError, ValueError, AttributeError) as e:
                raise BadGroupConfig(f'Group {group_name} has bad config') from e

            group = Group(
                name=group_name,
                enabled=group_enabled,
                start=group_start,
                deadline=group_deadline,
                second_deadline=group_second_deadline,
                marked=group_marked,
            )

            for task_config in group_config.get('tasks', []):
                task_name = None
                try:
                    task_name = task_config['task']
                    task_score = int(task_config['score'])
                    task_enabled = task_config.get('enabled', True)
                    task_scoring_func = task_config.get('scoring_func', 'max')
                    task_is_review = task_config.get('review', False)
                    task_marked = task_config.get('marked', False) or group_marked
                except (KeyError, TypeError, ValueError, AttributeError) as e:
                    raise BadTaskConfig(f'Task {task_name} has bad config') from e

                task = Task(
                    group=group,
                    name=task_name,
                    max_score=task_score,
                    enabled=task_enabled,
                    scoring_func=task_scoring_func,
                    review=task_is_review,
                    marked=task_marked,
                )

                if task_name in self.tasks:
                    raise BadTaskConfig(f'Unique violation error: task {task_name} already exists')

                self.tasks[task_name] = task
                group.tasks.append(task)

            if group_name in self.groups:
                raise BadGroupConfig(f'Unique violation error: group {group_name} already exists')

            self.groups[group_name] = group

    def get_tasks(
            self,
            *,
            enabled: bool | None = None,
            started: bool | None = None,
            ended: bool | None = None,
    ) -> list[Task]:
        tasks: list[Task] = [task for task_name, task in self.tasks.items()]

        if enabled is not None:
            tasks = [task for task in tasks if (task.is_enabled and task.group.is_enabled) == enabled]
        if started is not None:
            tasks = [task for task in tasks if task.group.is_started == started]
        if ended is not None:
            tasks = [task for task in tasks if task.group.is_ended == ended]

        return tasks

    def get_groups(
            self,
            *,
            enabled: bool | None = None,
            started: bool | None = None,
            ended: bool | None = None,
    ) -> list[Group]:
        groups: list[Group] = [group for group_name, group in self.groups.items()]

        if enabled is not None:
            groups = [group for group in groups if group.is_enabled == enabled]
        if started is not None:
            groups = [group for group in groups if group.is_started == started]
        if ended is not None:
            groups = [group for group in groups if group.is_ended == ended]

        return groups
