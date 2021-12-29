import subprocess
from pathlib import Path
from typing import Union

from ..course import Course, PUBLIC_DIR
from ..utils import print_info


def render_lectures(course: Course, dry_run: bool = False, build_dir: Union[str, Path] = 'lectures_build') -> None:
    """Render lectures from lectures dir from Course to `build` folder"""
    if isinstance(build_dir, str):
        build_dir = PUBLIC_DIR / build_dir

    # list enabled task folders ready for deploy
    lecture_folders: set[Path] = {
        group.lectures_dir for group in course.get_groups(started=True) if group.lectures_dir.exists()
    }

    for lecture_folder in lecture_folders:
        ipynb_files = lecture_folder.glob('*.ipynb')
        if dry_run:
            print_info('lecture_folder:', lecture_folder)
            print_info('  ipynb_files:', list(ipynb_files))
        else:
            for ipynb_file in ipynb_files:
                subprocess.run(
                    f'python -m jupyter nbconvert --to html --output-dir {build_dir.as_posix()} {ipynb_file}',
                    encoding='utf-8',
                    stdout=subprocess.PIPE,
                    shell=True
                )
            if (lecture_folder / 'images').exists():
                subprocess.run(
                    f'mkdir -p lectures_build/images/ && cp -R {lecture_folder / "images"} {build_dir / "images"}',
                    encoding='utf-8',
                    stdout=subprocess.PIPE,
                    shell=True
                )
