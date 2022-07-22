from pathlib import Path


def filename_match_patterns(file: Path, patterns: list[str]) -> bool:
    for pattern in patterns:
        if file.match(pattern):
            return True
    return False
