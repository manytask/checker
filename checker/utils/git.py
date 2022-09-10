import shutil
import subprocess
from pathlib import Path

from .print import print_info

DEFAULT_BRANCH = 'main'


def setup_repo_in_dir(
        repo_dir: Path,
        remote_repo_url: str,
        service_username: str,
        service_token: str,
        git_user_email: str = 'no-reply@gitlab.manytask.org',
        git_user_name: str = 'Manytask Bot',
        branch: str = DEFAULT_BRANCH,
) -> None:
    remote_repo_url = remote_repo_url.replace('https://', '').replace('http://', '').replace('.git', '')
    print_info(f'remote_repo_url {remote_repo_url}', color='grey')

    shutil.rmtree(repo_dir)
    repo_dir.mkdir()

    print_info('* git clone...')
    t = subprocess.run(
        f'git clone --depth=1 --branch={branch} https://{service_username}:{service_token}@{remote_repo_url}.git ./',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    ).stdout
    print_info(t, color='grey')

    print_info('* git remote...')
    t = subprocess.run(
        'git remote -v',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    ).stdout
    print_info(t, color='grey')

    print_info('* git config set...')
    t = subprocess.run(
        f'git config --local user.email "{git_user_email}" && '
        f'git config --local user.name "{git_user_name}"',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    ).stdout
    print_info(t, color='grey')


def commit_push_all_repo(
        repo_dir: Path,
        branch: str = DEFAULT_BRANCH,
        message: str = 'Export public files',
) -> None:
    print_info('* git status...')
    t = subprocess.run(
        'git status',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    ).stdout
    print_info(t, color='grey')

    print_info('* adding files...')
    t = subprocess.run(
        'git add .',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    ).stdout
    print_info(t, color='grey')

    print_info('* committing...')
    t = subprocess.run(
        f'git commit --all -m "{message}"',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    ).stdout
    print_info(t, color='grey')

    print_info('* git pushing...')
    t = subprocess.run(
        f'git push -o ci.skip origin {branch}',
        encoding='utf-8',
        stdout=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
    ).stdout
    print_info(t, color='grey')

    print_info('Done.')
