from __future__ import annotations

import os
from typing import Any
from pathlib import Path

import gitlab

from .print import print_info


GITLAB_HOST_URL = 'https://gitlab.manytask.org'
GITLAB_TOKEN = os.environ.get('PYTHON_COURSE_API_TOKEN', None)
GITLAB_TOKEN = GITLAB_TOKEN or os.environ.get('CI_JOB_TOKEN', None)

GITLAB = gitlab.Gitlab(GITLAB_HOST_URL, GITLAB_TOKEN)


STUDENTS_GROUP_NAME = 'python-fall-2021'
PRIVATE_GROUP_NAME = 'py-tasks'

PRIVATE_REPO_NAME = 'private-tasks'
PUBLIC_REPO_NAME = 'public-2021-fall'

MASTER_BRANCH = 'master'


def get_project_from_group(group_name: str, project_name: str) -> Any:
    print_info("Get private Project", color='grey')

    _groups = GITLAB.groups.list(search=group_name)
    assert len(_groups) == 1, f'Could not find group_name={group_name}'
    group = _groups[0]

    project = {i.name: i for i in group.projects.list(all=True)}[project_name]

    print_info(f"Got private project: <{project.name}>", color='grey')

    return project


def get_private_project() -> Any:
    return get_project_from_group(PRIVATE_GROUP_NAME, PRIVATE_REPO_NAME)


def get_public_project() -> Any:
    return get_project_from_group(PRIVATE_GROUP_NAME, PUBLIC_REPO_NAME)


def get_projects_in_group(group_name: str) -> list[Any]:
    print_info(f"Get projects in group_name={group_name}", color='grey')

    _groups = GITLAB.groups.list(search=group_name)
    assert len(_groups) == 1, f'Could not find group_name={group_name}'
    group = _groups[0]

    print_info(f"Got group: <{group.name}>", color='grey')

    projects = group.projects.list(all=True)

    print_info(f"Got {len(projects)} projects", color='grey')

    return projects


def get_group_members(group_name: str) -> list[Any]:
    print_info(f"Get members in group_name={group_name}", color='grey')

    _groups = GITLAB.groups.list(search=group_name)
    assert len(_groups) == 1, f'Could not find group_name={group_name}'
    group = _groups[0]

    print_info(f"Got group: <{group.name}>", color='grey')

    members = group.members.list()

    print_info(f"Got {len(members)} members", color='grey')

    # users = [GITLAB.users.get(m.id) for m in members]
    #
    # print_info(f"Got {len(users)} users", color='grey')

    return members


def get_all_tutors() -> list[Any]:
    return get_group_members(PRIVATE_GROUP_NAME)


def get_students_projects() -> list[Any]:
    return get_projects_in_group(STUDENTS_GROUP_NAME)


def get_student_file_link(username: str, path: str | Path) -> str:
    return f'{GITLAB_HOST_URL}/{STUDENTS_GROUP_NAME}/{username}/-/blob/{MASTER_BRANCH}/{path}'
