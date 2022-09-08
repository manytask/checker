# type: ignore
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import gitlab.v4.objects

from ..course import CourseConfig
from ..utils.glab import GITLAB, GITLAB_HOST_URL, MASTER_BRANCH, get_private_project, get_public_project
from ..utils.print import print_info

MR_COPY_TOKEN = os.environ.get('MR_COPY_TOKEN')


def _student_mr_title_generator(merge_request: gitlab.v4.objects.MergeRequest) -> str:
    iid = merge_request.iid
    title = merge_request.title
    username = merge_request.author['username']

    return f'[STUDENT {username} MR {iid}] {title}'


def _get_student_mr_title_prefix(full_title: str) -> str:
    _title_search = re.match(r'^[.*]', full_title)
    assert _title_search
    prefix = _title_search.group(0)
    return prefix


def _student_mr_branch_name_generator(merge_request: gitlab.v4.objects.MergeRequest) -> str:
    iid = merge_request.iid
    username = merge_request.author['username']
    return f'students/{username}/mr-{iid}'


def _student_mr_desc_generator(merge_request: gitlab.v4.objects.MergeRequest) -> str:
    source_branch = merge_request.source_branch
    target_branch = merge_request.target_branch
    iid = merge_request.iid
    title = merge_request.title
    url = merge_request.web_url
    description = merge_request.description
    username = merge_request.author['username']
    name = merge_request.author['name']
    user_url = merge_request.author['web_url']
    return '  \n'.join([
        f'Contribution by student [{username}]({user_url}): {name}',
        '-'*16,
        f'Original [MR{iid}]({url}) from {source_branch} to {target_branch} in public project',
        f'Title: {title}',
        f'Branch: {source_branch}',
        '',
        f'{description}',
    ])


def _get_student_mr_source_url(merge_request: gitlab.v4.objects.MergeRequest) -> tuple[str, str]:
    source_project_id = merge_request.source_project_id
    full_project = GITLAB.projects.get(source_project_id)

    source_branch = merge_request.source_branch

    return ''.join([
        'https://',
        f'kblack:{MR_COPY_TOKEN}@',
        GITLAB_HOST_URL.removeprefix('https://'),
        '/',
        full_project.path_with_namespace,
    ]), source_branch


def copy_merge_requests(course_config: CourseConfig, dry_run: bool = False) -> None:
    """Copy changes from all open MR"""
    raise NotImplementedError

    private_project = get_private_project(course_config.private_group, course_config.private_repo)
    full_private_project = GITLAB.projects.get(private_project.id)
    public_project = get_public_project(course_config.private_group, course_config.public_repo)
    full_public_project = GITLAB.projects.get(public_project.id)

    # Run rebase
    print_info('Go and rebase public project', color='pink')
    public_mrs = full_public_project.mergerequests.list(state='opened')
    for mr in public_mrs:
        print_info(f'Rebase public MR {mr.iid} "{mr.title}":', color='pink')
        # mr.notes.create({'body': 'Run auto rebase...'})
        print_info(mr, color='grey')
        rebase_in_progress = mr.rebase()['rebase_in_progress']
        print_info("rebase_in_progress", rebase_in_progress)

    print_info('Waiting until rebase done...', color='pink')
    time.sleep(60)  # TODO: add check

    stdout = subprocess.run(
        'git fetch private',
        encoding='utf-8',
        shell=True, check=True,
        stdout=subprocess.PIPE,
    ).stdout
    print_info(stdout, color='grey')

    private_mrs = full_private_project.mergerequests.list(state='opened')
    private_students_mr = {
        prefix_match.group(0): mr for mr in private_mrs if (prefix_match := re.match(r'^\[.*\]', mr.title))
    }
    print_info('private_students_mr', len(private_students_mr), private_students_mr.keys())

    public_mrs = full_public_project.mergerequests.list(state='opened')

    print_info('Throughout public MR', color='pink')
    for mr in public_mrs:
        full_mr = GITLAB.mergerequests.get(mr.id)
        print_info('full_mr', full_mr)
        print_info(f'Look up public MR {mr.iid} "{mr.title}":', color='pink')
        print_info(mr, color='grey')

        gen_mr_full_title = _student_mr_title_generator(mr)
        gen_mr_prefix = _get_student_mr_title_prefix(gen_mr_full_title)

        if gen_mr_prefix in private_students_mr:
            print_info(f'MR "{gen_mr_prefix}" exists. Updating it...')
            # Already exists. Get branch name
            private_mr = private_students_mr[gen_mr_prefix]
            private_branch_name = private_mr.source_branch

            # An checkout existed branch
            print_info(f'checkout {private_branch_name}...')
            stdout = subprocess.run(
                f'git checkout --force --track private/{private_branch_name}',
                encoding='utf-8',
                shell=True, check=True,
                stdout=subprocess.PIPE,
            ).stdout
            print_info(stdout, color='grey')

            # Update desc and so on
            print_info('updating mr...')
            private_mr.title = _student_mr_title_generator(mr)
            private_mr.description = _student_mr_desc_generator(mr)
            private_mr.labels = ['contributing']
            private_mr.save()
            print_info('private_mr', private_mr, color='grey')
        else:
            # Not exist. So create
            print_info(f'MR "{gen_mr_prefix}" not exists. Creating it...')
            private_branch_name = _student_mr_branch_name_generator(mr)

            # Create and push branch
            print_info(f'create and checkout {private_branch_name}...')
            stdout = subprocess.run(
                f'git checkout --force -b {private_branch_name} private/{MASTER_BRANCH} '
                f'&& git push --set-upstream  private {private_branch_name}',
                encoding='utf-8',
                shell=True, check=True,
                stdout=subprocess.PIPE,
            ).stdout
            print_info(stdout, color='grey')

            # Create a MR
            print_info('creating mr...')
            private_mr = full_private_project.mergerequests.create({
                'source_branch': private_branch_name,
                'target_branch': MASTER_BRANCH,
                'title': _student_mr_title_generator(mr),
                'description': _student_mr_desc_generator(mr),
                'labels': ['contributing'],
                'remove_source_branch': True,
                'squash': True,
                'allow_maintainer_to_push': True,
            })
            print_info('private_mr', private_mr, color='grey')

        # Del processed private MR (leave only outdated)
        if gen_mr_prefix in private_students_mr:
            del private_students_mr[gen_mr_prefix]

        print_info(f'git status in {private_branch_name}:')
        stdout = subprocess.run(
            'git status',
            encoding='utf-8',
            shell=True, check=True,
            stdout=subprocess.PIPE,
        ).stdout
        print_info('Current status:', color='grey')
        print_info(stdout, color='grey')

        tmp_dir = TemporaryDirectory(dir=Path('.'))
        tmp_dir_path = tmp_dir.name
        # print_info(f'clone changes in {private_branch_name} from public mr:')
        # tmp_dir_path = mkdtemp(dir=Path('.'))

        source_url, source_branch = _get_student_mr_source_url(mr)
        # print(source_url, source_branch, tmp_dir_path)

        # Clone single branch in tmp folder
        # TODO: not copy, but merge
        print_info('Clone and update files...')
        stdout = subprocess.run(
            f'git clone --depth=1 --branch {source_branch} {source_url} {tmp_dir_path} && rm -rf {tmp_dir_path}/.git &&'
            f'cp -a {tmp_dir_path}/* ./ && rm -rf {tmp_dir_path}',
            # f'mv -f {tmp_dir_path}/* . && rm -rf {tmp_dir_path}',
            encoding='utf-8',
            shell=True, check=True,
            stdout=subprocess.PIPE,
        ).stdout
        print_info(stdout, color='grey')

        stdout = subprocess.run(
            'git status',
            encoding='utf-8',
            shell=True, check=True,
            stdout=subprocess.PIPE,
        ).stdout
        print_info('Current status:', color='grey')
        print_info(stdout, color='grey')

        # Git add only modified and deleted
        print_info('Git add modified and commit and push it...')
        stdout = subprocess.run(
            'git add -u',
            encoding='utf-8',
            shell=True, check=True,
            stdout=subprocess.PIPE,
        ).stdout
        print_info(stdout, color='grey')

        stdout = subprocess.run(
            'git status && git branch',
            encoding='utf-8',
            shell=True, check=True,
            stdout=subprocess.PIPE,
        ).stdout
        print_info('git status && git branch', color='grey')
        print_info(stdout, color='grey')

        stdout = subprocess.run(
            f'git commit -m "Export mr files" --allow-empty && git push --set-upstream private {private_branch_name}',
            encoding='utf-8',
            shell=True, check=True,
            stdout=subprocess.PIPE,
        ).stdout
        print_info(stdout, color='grey')

    print_info('Deleting outdated private MR', color='pink')
    for mr in private_students_mr:
        print_info(f'Deleting outdated MR {mr.iid} {mr.title}...')
        # mr.state_event = 'close'
        # mr.save()
        mr.delete()


def create_public_mr(
        course_config: CourseConfig,
        object_attributes: dict[str, str] | None = None,
        *,
        dry_run: bool = False,
) -> None:
    """Copy changes from public repo"""
    raise NotImplementedError

    object_attributes = object_attributes or {}
    merge_commit_sha = object_attributes['merge_commit_sha']
    title = object_attributes['title']
    url = object_attributes['url']
    iid = object_attributes['iid']
    description = object_attributes['description']
    author_id = object_attributes['author_id']
    updated_at = object_attributes['updated_at']

    private_project = get_private_project(course_config.private_group, course_config.private_repo)
    full_private_project = GITLAB.projects.get(private_project.id)
    # public_project = get_public_project()
    # full_public_project = GITLAB.projects.get(public_project.id)
    author = GITLAB.users.get(author_id)

    # Get public project sha and generate branch name
    if merge_commit_sha:
        public_sha = merge_commit_sha
    else:
        public_sha = subprocess.run(
            f"git log public/{MASTER_BRANCH} --pretty=format:'%H' -n 1",
            encoding='utf-8',
            shell=True, check=True,
            stdout=subprocess.PIPE,
        ).stdout
    print_info(f'public/{MASTER_BRANCH}: {title} (sha {public_sha})')
    new_branch_name = f'public/mr-{iid}'
    new_title = f'[PUBLIC] {title}'
    new_description = '  \n'.join([
        f'Merged public project [MR{iid}]({url})',
        f'author: {author.username} - {author.name}',
        f'updated_at: {updated_at}',
        f'sha: {public_sha}',
        '',
        description,
    ])

    # Get all mrs from private repo
    private_mrs = full_private_project.mergerequests.list(state='opened')
    private_mrs = {mr.title: mr for mr in private_mrs if '[PUBLIC]' in mr.title}

    if new_title in private_mrs:
        # Already exists
        mr = private_mrs[new_title]
        print_info(f'MR with sha {public_sha} already exists!')
        print_info(mr, color='grey')
        return
    else:
        # Not exist

        # Create branch
        print_info('Create branch from remote', color='grey')
        stdout = subprocess.run(
            f'git checkout --force -b {new_branch_name} private/{MASTER_BRANCH}',
            encoding='utf-8',
            shell=True, check=True,
            stdout=subprocess.PIPE,
        ).stdout
        print_info(stdout, color='grey')

        print_info(f'Merge from public (by sha {public_sha[:7]})', color='grey')
        stdout = subprocess.run(
            # f'git merge -s ours --allow-unrelated-histories --no-commit public/{MASTER_BRANCH}',
            f'git merge --strategy-option=theirs --allow-unrelated-histories --no-commit {public_sha}',
            encoding='utf-8',
            shell=True, check=True,
            stdout=subprocess.PIPE,
        ).stdout
        print_info(stdout, color='grey')

        # Check diff not empty
        stdout = subprocess.run(
            'git status',
            encoding='utf-8',
            shell=True, check=True,
            stdout=subprocess.PIPE,
        ).stdout
        print_info(stdout, color='grey')

        if 'Changes to be committed:' not in stdout:
            print_info(
                f'Can not create MR. No changes to commit between {MASTER_BRANCH} and public/{MASTER_BRANCH}',
                color='orange'
            )
            return

        # Git add only modified and deleted
        print_info('Git add modified and commit and push it...')
        stdout = subprocess.run(
            f'git commit -m "{new_title}" && git push private {new_branch_name}',
            encoding='utf-8',
            shell=True, check=True,
            stdout=subprocess.PIPE,
        ).stdout
        print_info(stdout, color='grey')

        # Create mr
        mr = full_private_project.mergerequests.create({
            'source_branch': new_branch_name,
            'target_branch': MASTER_BRANCH,
            'title': new_title,
            'description': new_description,
            'labels': ['public'],
            'remove_source_branch': True,
            'squash': True,
            'allow_maintainer_to_push': True,
        })

        print_info('Ok. New MR created', color='green')
        print_info(mr.web_url)
