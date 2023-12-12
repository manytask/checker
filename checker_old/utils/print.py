from __future__ import annotations

import sys
from typing import Any


def print_info(
        *args: Any,
        file: Any = None,
        color: str | None = None,
        **kwargs: Any,
) -> None:
    colors = {
        'white': '\033[97m',
        'cyan': '\033[96m',
        'pink': '\033[95m',
        'blue': '\033[94m',
        'orange': '\033[93m',
        'green': '\033[92m',
        'red': '\033[91m',
        'grey': '\033[90m',
        'endc': '\033[0m',
    }

    file = file or sys.stderr

    data = ' '.join(map(str, args))
    if color in colors:
        print(colors[color] + data + colors['endc'], file=file, **kwargs)
    else:
        print(data, file=file, **kwargs)
    file.flush()


def print_header_info(
        info_string: str,
) -> None:
    info_extended_string = ' ' + info_string + ' '
    info_extended_string = '+' * (50 - len(info_extended_string) // 2) + \
                           info_extended_string + \
                           '+' * (50 - len(info_extended_string) // 2)
    print_info('')
    print_info('+' * len(info_extended_string), color='pink')
    print_info(info_extended_string, color='pink')
    print_info('+' * len(info_extended_string), color='pink')


def print_task_info(
        task_name: str,
) -> None:
    print_header_info(f'Testing tasks: <{task_name}>')
