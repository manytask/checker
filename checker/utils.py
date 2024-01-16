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
        "white": "\033[97m",
        "cyan": "\033[96m",
        "pink": "\033[95m",
        "blue": "\033[94m",
        "orange": "\033[93m",
        "green": "\033[92m",
        "red": "\033[91m",
        "grey": "\033[90m",
        "endc": "\033[0m",
    }

    file = file or sys.stderr

    data = " ".join(map(str, args))
    if color in colors:
        print(colors[color] + data + colors["endc"], file=file, **kwargs)
    else:
        print(data, file=file, **kwargs)
    file.flush()


def print_separator(
    symbol: str,
    file: Any = None,
    color: str = "pink",
    string_length: int = 80,
) -> None:
    print_info(symbol * string_length, color=color)


def print_header_info(
    header_string: str,
    file: Any = None,
    color: str = "pink",
    string_length: int = 80,
    **kwargs: Any,
) -> None:
    info_extended_string = " " + header_string + " "
    print_info("", file=file)
    print_separator(symbol="+", string_length=string_length, color=color, file=file)
    print_info(f"{info_extended_string:+^{string_length}}", color=color, file=file)
    print_separator(symbol="+", string_length=string_length, color=color, file=file)
