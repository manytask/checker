"""
All course configurations
Include tests, layout, manytask url, gitlab urls, etc. settings
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from ..exceptions import BadConfig


@dataclass
class CourseConfig:
    # main course settings
    name: str
    deadlines: str
    system: str

    # manytask
    manytask_url: str

    # gitlab
    students_group: str
    private_group: str
    private_repo: str
    public_repo: str
    lectures_repo: str | None = None
    gitlab_url: str = 'https://gitlab.manytask.org'

    # layout
    layout: str = 'groups'
    # executor
    executor: str = 'sandbox'

    @classmethod
    def from_yaml(cls, course_config: Path) -> 'CourseConfig':
        try:
            with open(course_config) as config_file:
                config = yaml.safe_load(config_file)
        except (yaml.YAMLError, FileNotFoundError) as e:
            raise BadConfig(f'Unable to load deadlines config file <{course_config}>') from e

        try:
            return cls(**config)
        except (KeyError, TypeError, ValueError) as e:
            raise BadConfig('Invalid course config') from e
