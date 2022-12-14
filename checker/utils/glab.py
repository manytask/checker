from __future__ import annotations

import typing
from pathlib import Path

import gitlab
import gitlab.v4.objects

from .print import print_info


class GitlabConnection:
    def __init__(
            self,
            gitlab_host_url: str,
            api_token: str | None = None,
            private_token: str | None = None,
            job_token: str | None = None,
    ):
        if api_token:
            self.gitlab = gitlab.Gitlab(gitlab_host_url, private_token=api_token)
        elif private_token:
            self.gitlab = gitlab.Gitlab(gitlab_host_url, private_token=private_token)
        elif job_token:
            self.gitlab = gitlab.Gitlab(gitlab_host_url, job_token=job_token)
        else:
            print_info(
                'None of `api_token`/`private_token` or `job_token` provided; use without credentials',
                color='orange',
            )
            self.gitlab = gitlab.Gitlab(gitlab_host_url)

    def get_project_from_group(
            self,
            group_name: str,
            project_name: str,
    ) -> gitlab.v4.objects.GroupProject:
        print_info('Get private Project', color='grey')

        _groups = self.gitlab.groups.list(get_all=True, search=group_name)

        print_info(_groups, color='grey')
        assert len(_groups) >= 1, f'Could not find group_name={group_name}'
        group = _groups[0]  # type: ignore

        project = {i.name: i for i in group.projects.list(all=True)}[project_name]

        project = typing.cast(gitlab.v4.objects.GroupProject, project)
        print_info(f'Got private project: <{project.name}>', color='grey')

        return project

    def get_public_project(
            self,
            private_group_name: str,
            public_repo_name: str,
    ) -> gitlab.v4.objects.GroupProject:
        return self.get_project_from_group(private_group_name, public_repo_name)

    def get_projects_in_group(
            self,
            group_name: str,
    ) -> list[gitlab.v4.objects.GroupProject]:
        print_info(f'Get projects in group_name={group_name}', color='grey')

        _groups = self.gitlab.groups.list(get_all=True, search=group_name)

        assert len(_groups) >= 1, f'Could not find group_name={group_name}'
        group = _groups[0]  # type: ignore

        print_info(f'Got group: <{group.name}>', color='grey')

        projects = group.projects.list(all=True)

        projects = typing.cast(list[gitlab.v4.objects.GroupProject], projects)
        print_info(f'Got {len(projects)} projects', color='grey')

        return projects

    def get_group_members(
            self,
            group_name: str,
    ) -> list[gitlab.v4.objects.GroupMember]:
        print_info(f'Get members in group_name={group_name}', color='grey')

        _groups = self.gitlab.groups.list(get_all=True, search=group_name)

        print_info(_groups, color='grey')
        assert len(_groups) >= 1, f'Could not find group_name={group_name}'
        group = _groups[0]  # type: ignore

        print_info(f'Got group: <{group.name}>', color='grey')

        members = group.members_all.list(all=True, get_all=True)

        members = typing.cast(list[gitlab.v4.objects.GroupMember], members)
        print_info(f'Got {len(members)} members', color='grey')

        return members

    def get_project_members(
            self,
            project_name: str,
    ) -> list[gitlab.v4.objects.ProjectMember]:
        print_info(f'Get members in project_name={project_name}', color='grey')

        _projects = self.gitlab.projects.list(get_all=True, search=project_name)

        assert len(_projects) >= 1, f'Could not find project_name={project_name}'
        project = _projects[0]  # type: ignore

        print_info(f'Got project: <{project.name}>', color='grey')

        members = project.members_all.list(all=True, get_all=True)

        members = typing.cast(list[gitlab.v4.objects.ProjectMember], members)
        print_info(f'Got {len(members)} members', color='grey')

        return members

    def get_user_by_username(
            self,
            username: str,
    ) -> gitlab.v4.objects.User:
        print_info(f'Get user with username={username}', color='grey')

        _users = self.gitlab.users.list(get_all=True, search=username)
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
            user = _users[0]  # type: ignore

        user = typing.cast(gitlab.v4.objects.User, user)
        print_info(f'Got user: <{user.name}>', color='grey')

        return user

    def get_all_tutors(
            self,
            private_group_name: str,
    ) -> list[gitlab.v4.objects.GroupMember]:
        return self.get_group_members(private_group_name)

    def get_students_projects(
            self,
            students_group_name: str,
    ) -> list[gitlab.v4.objects.GroupProject]:
        return self.get_projects_in_group(students_group_name)

    def get_student_file_link(
            self,
            gitlab_url: str,
            default_branch: str,
            students_group_name: str,
            username: str,
            path: str | Path,
    ) -> str:
        return f'{gitlab_url}/{students_group_name}/{username}/-/blob/{default_branch}/{path}'

    def get_current_user(
            self,
    ) -> gitlab.v4.objects.CurrentUser:
        self.gitlab.auth()
        current_user = self.gitlab.user

        current_user = typing.cast(gitlab.v4.objects.CurrentUser, current_user)

        return current_user

    def get_group(
            self,
            name: str,
    ) -> gitlab.v4.objects.Group:
        print_info(f'Get group name={name}', color='grey')

        _groups = self.gitlab.groups.list(get_all=True, search=name)

        assert len(_groups) >= 1, f'Could not find group name={name}'
        group = _groups[0]  # type: ignore

        group = typing.cast(gitlab.v4.objects.Group, group)

        return group
