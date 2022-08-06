"""
All course configurations
Include tests, layout, manytask url, gitlab urls, etc. settings
"""
from __future__ import annotations

import os
from dataclasses import InitVar, dataclass
from pathlib import Path

import yaml

from ..exceptions import BadConfig
from ..utils.print import print_info


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
    default_branch: str = 'master'
    gitlab_url: str = 'https://gitlab.manytask.org'
    gitlab_service_username: str = 'manytask'

    # layout
    layout: str = 'groups'
    # executor
    executor: str = 'sandbox'

    # credentials
    manytask_token: str | None = None
    gitlab_service_token: str | None = None
    gitlab_api_token: str | None = None

    manytask_token_id: InitVar[str] = 'TESTER_TOKEN'
    gitlab_service_token_id: InitVar[str] = 'GITLAB_SERVICE_TOKEN'
    gitlab_api_token_id: InitVar[str] = 'GITLAB_API_TOKEN'

    def __post_init__(
            self,
            manytask_token_id: str,
            gitlab_service_token_id: str,
            gitlab_api_token_id: str,
    ) -> None:
        self.manytask_token = os.environ.get(manytask_token_id)
        if not self.manytask_token:
            print_info(f'Unable to find env <{manytask_token_id}>', color='orange')

        self.gitlab_service_token = os.environ.get(gitlab_service_token_id)
        if not self.gitlab_service_token:
            print_info(f'Unable to find env <{gitlab_service_token_id}>', color='orange')

        self.gitlab_api_token = os.environ.get(gitlab_api_token_id)
        if not self.gitlab_api_token:
            print_info(f'Unable to find env <{gitlab_api_token_id}>', color='orange')

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
