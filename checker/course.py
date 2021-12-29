"""All classes and functions interacting with course groups and tasks"""
import json
import re
from collections import OrderedDict
from dataclasses import dataclass, field, InitVar
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, Any

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = SCRIPT_DIR.parent.parent
PRIVATE_DIR = PUBLIC_DIR / 'tests'
LECTURES_DIR = PUBLIC_DIR / 'lectures'


@dataclass
class BadConfig(ValueError):
    name: str
    msg: str = ''

    def __str__(self):
        return f'{self.__class__.__name__}: {self.name} caused by <{self.msg}>'

    def __repr__(self):
        return f'{self.__class__.__name__}(name={self.name},msg={self.msg})'


class BadTaskConfig(BadConfig):
    pass


class BadGroupConfig(BadConfig):
    pass


class Task:
    @dataclass
    class TaskTestConfig:
        review: bool = False
        checklist: Optional[str] = None
        partially_scored: bool = False
        verbose_tests_output: bool = False
        module_test: bool = False
        build_wheel: bool = False
        run_mypy: bool = True

        forbidden_regexp: list[re.Pattern] = field(default_factory=list)

        public_test_files: list[str] = field(default_factory=list)
        private_test_files: list[str] = field(default_factory=list)
        test_files: list[str] = field(default_factory=list)

        test_timeout: Optional[int] = None  # seconds
        coverage: Union[bool, int] = False

        # Init only
        explicit_public_tests: InitVar[list[str]] = None
        explicit_private_tests: InitVar[list[str]] = None

        def __post_init__(
                self, explicit_public_tests: Optional[list[str]], explicit_private_tests: Optional[list[str]]
        ):
            self.forbidden_regexp += [r'exit\(0\)']
            for regexp in self.forbidden_regexp:
                re.compile(regexp)

            self.public_test_files = ['test_public.py'] + (explicit_public_tests or [])
            self.private_test_files = ['test_private.py'] + (explicit_private_tests or [])
            self.test_files = self.public_test_files + self.private_test_files

    def __init__(
            self,
            group: 'Group',
            name: str,
            max_score: int,
            scoring_func: str,
    ):
        self.group = group
        self.name = name
        self.full_name = self.group.name + '/' + self.name
        self.max_score = max_score
        self.scoring_func = scoring_func

        self.source_dir: Path = group.source_dir / self.name
        self.public_dir: Path = group.public_dir / self.name
        self.private_dir: Path = group.private_dir / self.name

        if not self.source_dir.exists() or not self.public_dir.exists() or not self.private_dir.exists():
            raise BadTaskConfig(
                name=self.name, msg=f'Task {self.name} in group {self.group.name} miss source or public or private dir'
            )

        try:
            task_config_path = self.private_dir / '.tester.json'
            if task_config_path.exists():
                with open(task_config_path) as f:
                    raw_config = json.load(f)
                if not isinstance(raw_config, dict):
                    raise TypeError(f"Got '{type(raw_config).__name__}' instead of 'dict'")
            else:
                raw_config = {}
        except (json.JSONDecodeError, TypeError) as e:
            raise BadTaskConfig(name=self.name) from e

        # Go throughout config fields and pop it from json if any
        config_kwargs: dict[str, Any] = {}
        for config_field in self.TaskTestConfig.__annotations__:
            if (field_value := raw_config.pop(config_field, None)) is not None:
                config_kwargs[config_field] = field_value

        self.config = self.TaskTestConfig(**config_kwargs)

        if raw_config:
            bad_keys = "', '".join(raw_config.keys())
            raise BadTaskConfig(name=self.name, msg=f"Unknown key(s) '{bad_keys}'")


class Group:
    def __init__(
            self,
            name: str,
            enabled: bool,
            start: datetime,
            deadline: datetime,
            second_deadline: datetime,
            source_dir: Path,
            public_dir: Path,
            private_dir: Path,
            lectures_dir: Path,
    ):
        self.name = name

        self.start = start
        self.deadline = deadline
        self.second_deadline = second_deadline

        self.is_enabled = enabled
        self.is_started = self.is_enabled and self.start < datetime.now()  # TODO: check timezone
        self.is_ended = self.second_deadline < datetime.now()  # TODO: check timezone

        self.tasks = []

        self.source_dir: Path = source_dir / name
        self.public_dir: Path = public_dir / name
        self.private_dir: Path = private_dir / name
        self.lectures_dir: Path = lectures_dir / name

        self.is_source_valid = self.source_dir.exists()
        self.is_task_valid = self.public_dir.exists() and self.private_dir.exists()


class Course:
    def __init__(
            self,
            config_path: Path = PRIVATE_DIR / '.deadlines.yml',
            source_dir: Path = PUBLIC_DIR,
            public_dir: Path = PUBLIC_DIR,
            private_dir: Path = PRIVATE_DIR,
            lectures_dir: Path = LECTURES_DIR,
            skip_missed_sources: bool = False,
    ):
        self.source_dir: Path = source_dir
        self.public_dir: Path = public_dir
        self.private_dir: Path = private_dir
        self.lectures_dir: Path = lectures_dir

        try:
            with open(config_path) as config_file:
                config = yaml.safe_load(config_file)
        except (yaml.YAMLError, FileNotFoundError) as err:
            raise BadConfig() from err

        self.groups = OrderedDict()
        self.tasks = OrderedDict()

        for group_config in config:
            group_name = None
            try:
                group_name = str(group_config.get('group'))
                group_enabled = bool(group_config.get('enabled', True))

                group_start = datetime.strptime(group_config.get('start'), "%d-%m-%Y %H:%M")
                group_deadline = datetime.strptime(group_config.get('deadline'), "%d-%m-%Y %H:%M")
                _group_second_deadline = group_config.get('second_deadline', None)
                group_second_deadline = datetime.strptime(_group_second_deadline, "%d-%m-%Y %H:%M") \
                    if _group_second_deadline else group_deadline
            except (KeyError, TypeError, ValueError) as err:
                raise BadGroupConfig(group_name, msg=f'Group {group_name} has bad config') from err

            group = Group(
                name=group_name,
                enabled=group_enabled,
                start=group_start,
                deadline=group_deadline,
                second_deadline=group_second_deadline,
                source_dir=source_dir,
                public_dir=public_dir,
                private_dir=private_dir,
                lectures_dir=lectures_dir,
            )

            if group.is_started or group.is_enabled:
                _status = 'Started' if group.is_started else 'Enabled'
                if not group.is_source_valid:
                    if skip_missed_sources:
                        continue  # students repo without enabled tasks

                    raise BadGroupConfig(
                        group_name,
                        msg=f'{_status} Group {group_name} missed source dir'
                    )

                if not group.is_task_valid:
                    raise BadGroupConfig(
                        group_name,
                        msg=f'{_status} Group {group_name} miss public or private dir'
                    )
            else:
                continue

            for task_config in group_config.get('tasks', []):
                task_name = None
                try:
                    task_name = task_config['task']
                    task_score = int(task_config['score'])
                    task_scoring_func = task_config.get('scoring_func', 'max')
                except (KeyError, TypeError, ValueError) as err:
                    raise BadTaskConfig(task_name, msg=f'Task {task_name} has bad config') from err

                if (not (group.source_dir / task_name).exists()) and skip_missed_sources:  # TODO: refactor
                    continue  # students repo without enabled tasks

                task = Task(
                    group=group,
                    name=task_name,
                    max_score=task_score,
                    scoring_func=task_scoring_func,
                )
                # TODO: add task enabled param. skip disabled tasks

                if task_name in self.tasks:
                    raise BadTaskConfig(task_name, msg=f'Unique violation error: task {task_name} already exists')

                self.tasks[task_name] = task
                group.tasks.append(task)

            if group_name in self.groups:
                raise BadGroupConfig(group_name, msg=f'Unique violation error: group {group_name} already exists')

            self.groups[group_name] = group

    def get_tasks(self, enabled: Optional[bool] = None, started: Optional[bool] = None,
                  ended: Optional[bool] = None) -> list[Task]:
        tasks: list[Task] = [task for task_name, task in self.tasks.items()]

        if enabled is not None:
            tasks = [task for task in tasks if task.group.is_enabled == enabled]
        if started is not None:
            tasks = [task for task in tasks if task.group.is_started == started]
        if ended is not None:
            tasks = [task for task in tasks if task.group.is_ended == ended]

        return tasks

    def get_groups(self, valid: Optional[bool] = None, enabled: Optional[bool] = None,
                   started: Optional[bool] = None, ended: Optional[bool] = None) -> list[Group]:
        groups: list[Group] = [group for group_name, group in self.groups.items()]

        if valid is not None:
            groups = [group for group in groups if group.is_task_valid == valid]
        if enabled is not None:
            groups = [group for group in groups if group.is_enabled == enabled]
        if started is not None:
            groups = [group for group in groups if group.is_started == started]
        if ended is not None:
            groups = [group for group in groups if group.is_ended == ended]

        return groups
