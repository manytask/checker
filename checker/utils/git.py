import shutil
import subprocess
from pathlib import Path

from .print import print_info

DEFAULT_BRANCH = 'master'


def setup_repo_in_dir(
        repo_dir: Path,
        remote_repo_url: str,
        alias: str,
        service_username: str,
        service_token: str,
        git_user_email: str = 'no-reply@gitlab.manytask.org',
        git_user_name: str = 'Manytask Bot',
        branch: str = DEFAULT_BRANCH,
) -> None:
    shutil.rmtree(repo_dir)
    repo_dir.mkdir()

    subprocess.run(
        'git init',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    )

    subprocess.run(
        f'git config --local init.defaultBranch {branch} && '
        f'git config --local user.email "{git_user_email}" && '
        f'git config --local user.name "{git_user_name}"',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    )

    remote_repo_url = remote_repo_url.replace('https://', '').replace('http://', '').replace('.git', '')
    subprocess.run(
        f'git remote add {alias} https://{service_username}:{service_token}@{remote_repo_url}.git',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    )

    subprocess.run(
        f'git pull --depth=1 {alias} {branch}',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    )


def commit_push_all_repo(
        repo_dir: Path,
        alias: str,
        branch: str = DEFAULT_BRANCH,
        message: str = 'Export public files',
) -> None:
    print_info('Git status...')
    t = subprocess.run(
        'git status',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    ).stdout
    print_info(t, color='grey')

    print_info('Adding files...')
    t = subprocess.run(
        'git add .',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    ).stdout
    print_info(t, color='grey')

    print_info('Commiting...')
    t = subprocess.run(
        f'git commit --all -m "{message}"',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    ).stdout
    print_info(t, color='grey')

    print_info('Git pushing...')
    t = subprocess.run(
        f'git push -o ci.skip {alias} {branch}',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    ).stdout
    print_info(t, color='grey')

    print_info('Done.')
