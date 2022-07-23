from __future__ import annotations

import os
from pathlib import Path

import gitlab
import gitlab.v4.objects

from .print import print_info


GITLAB_HOST_URL = 'https://gitlab.manytask.org'

GITLAB_API_TOKEN = os.environ.get('GITLAB_API_TOKEN', None)
GITLAB_JOB_TOKEN = os.environ.get('CI_JOB_TOKEN', None)

if GITLAB_API_TOKEN:
    GITLAB = gitlab.Gitlab(GITLAB_HOST_URL, private_token=GITLAB_API_TOKEN)
elif GITLAB_JOB_TOKEN:
    GITLAB = gitlab.Gitlab(GITLAB_HOST_URL, job_token=GITLAB_JOB_TOKEN)
else:
    print_info('Unable to find one of GITLAB_API_TOKEN or CI_JOB_TOKEN', color='orange')
    GITLAB = gitlab.Gitlab(GITLAB_HOST_URL)

MASTER_BRANCH = 'master'


def get_project_from_group(
        group_name: str,
        project_name: str,
) -> gitlab.v4.objects.GroupProject:
    print_info('Get private Project', color='grey')

    _groups: list[gitlab.v4.objects.GroupProject] = GITLAB.groups.list(search=group_name)
    assert len(_groups) == 1, f'Could not find group_name={group_name}'
    group = _groups[0]

    project = {i.name: i for i in group.projects.list(all=True)}[project_name]

    print_info(f'Got private project: <{project.name}>', color='grey')

    return project


def get_private_project(
        private_group_name: str,
        private_repo_name: str,
) -> gitlab.v4.objects.GroupProject:
    return get_project_from_group(private_group_name, private_repo_name)


def get_public_project(
        private_group_name: str,
        public_repo_name: str,
) -> gitlab.v4.objects.GroupProject:
    return get_project_from_group(private_group_name, public_repo_name)


def get_projects_in_group(
        group_name: str,
) -> list[gitlab.v4.objects.GroupProject]:
    print_info(f'Get projects in group_name={group_name}', color='grey')

    _groups = GITLAB.groups.list(search=group_name)
    assert len(_groups) == 1, f'Could not find group_name={group_name}'
    group = _groups[0]

    print_info(f'Got group: <{group.name}>', color='grey')

    projects = group.projects.list(all=True)

    print_info(f'Got {len(projects)} projects', color='grey')

    return projects


def get_group_members(
        group_name: str,
) -> list[gitlab.v4.objects.GroupMember]:
    print_info(f'Get members in group_name={group_name}', color='grey')

    _groups = GITLAB.groups.list(search=group_name)
    assert len(_groups) == 1, f'Could not find group_name={group_name}'
    group = _groups[0]

    print_info(f'Got group: <{group.name}>', color='grey')

    members = group.members.list()

    print_info(f'Got {len(members)} members', color='grey')

    # users = [GITLAB.users.get(m.id) for m in members]
    #
    # print_info(f'Got {len(users)} users', color='grey')

    return members


def get_user_by_username(
        username: str,
) -> gitlab.v4.objects.User:
    print_info(f'Get user with username={username}', color='grey')

    _users = GITLAB.users.list(search=username)
    assert len(_users) > 0, f'Could not find username={username}'

    if len(_users) > 1:
        print_info(
            f'Got multiple users: <{[(user.username, user.name) for user in _users]}>',
            color='grey'
        )
        _username_to_user = {user.username: user for user in _users}
        assert username in _username_to_user, f'Could not find username={username}'
        user = _username_to_user[username]
    else:
        user = _users[0]

    print_info(f'Got user: <{user.name}>', color='grey')

    return user


def get_all_tutors(
        private_group_name: str,
) -> list[gitlab.v4.objects.GroupMember]:
    return get_group_members(private_group_name)


def get_students_projects(
        students_group_name: str,
) -> list[gitlab.v4.objects.GroupProject]:
    return get_projects_in_group(students_group_name)


def get_student_file_link(
        gitlab_url: str,
        students_group_name: str,
        username: str,
        path: str | Path,
) -> str:
    return f'{gitlab_url}/{students_group_name}/{username}/-/blob/{MASTER_BRANCH}/{path}'


def get_current_user() -> gitlab.v4.objects.CurrentUser:
    GITLAB.auth()
    current_user = GITLAB.user

    return current_user


def get_group(
        name: str,
) -> gitlab.v4.objects.Group:
    print_info(f'Get group name={name}', color='grey')

    _groups = GITLAB.groups.list(search=name)
    assert len(_groups) == 1, f'Could not find group name={name}'
    group = _groups[0]

    return group
