import stat
from pathlib import Path

import pytest

from checker.exceptions import BuildFailedError, StylecheckFailedError, TestsFailedError
from checker.testers.cpp import CppTester
from checker.utils import copy_files

cpp_tests = pytest.mark.skipif("not config.getoption('cpp')")

@pytest.fixture(scope='function')
def cpp_tester() -> CppTester:
    return CppTester(cleanup=True, dry_run=False)


def init_task(tmp_path: Path, code: str):
    course_dir = Path(__file__).parent / 'test_cpp_course'
    reference_dir = tmp_path / 'reference'
    root_dir = tmp_path / 'student'
    copy_files(course_dir, reference_dir)
    copy_files(course_dir, root_dir)

    source_dir = root_dir / 'foo'
    public_tests_dir = reference_dir / 'foo'
    private_tests_dir = reference_dir / 'tests' / 'foo'
    with open(source_dir / 'foo.h', 'w') as f:
        f.write(code)

    format_path = reference_dir / 'run-clang-format.py'
    format_path.chmod(format_path.stat().st_mode | stat.S_IEXEC)
    return source_dir, public_tests_dir, private_tests_dir


STAGE_BUILD = 1
STAGE_CLANG_FORMAT = 2
STAGE_CLANG_TIDY = 3
STAGE_TEST = 4
STAGE_UNREACHABLE = 6

def check_fail_on_stage(capsys: pytest.CaptureFixture[str], stage: int):
    messages = [
        'Running cmake...',
        'Building test_foo...',
        'Running clang format...',
        'Running clang tidy...',
        'Running test_foo...',
        'All tests passed'
    ]
    err = capsys.readouterr().err
    for i, message in enumerate(messages):
        if i <= stage:
            assert message in err
        else:
            assert message not in err


@cpp_tests
class TestCppTester:
    def test_simple(
            self,
            tmp_path: Path,
            cpp_tester: CppTester,
            capsys: pytest.CaptureFixture[str],
    ) -> None:
        code = 'int Foo() {\n    return 42;\n}\n'
        cpp_tester.test_task(*init_task(tmp_path, code))
        check_fail_on_stage(capsys, STAGE_UNREACHABLE)

    def test_clang_format_error(
            self,
            tmp_path: Path,
            cpp_tester: CppTester,
            capsys: pytest.CaptureFixture[str],
    ) -> None:
        code = 'int Foo() {\n  return 42;\n}\n'
        with pytest.raises(StylecheckFailedError):
            cpp_tester.test_task(*init_task(tmp_path, code))
        check_fail_on_stage(capsys, STAGE_CLANG_FORMAT)

    def test_clang_tidy_error(
            self,
            tmp_path: Path,
            cpp_tester: CppTester,
            capsys: pytest.CaptureFixture[str],
    ) -> None:
        code = 'int Foo() {\n    auto A = 42;\n    return A;\n}\n'
        with pytest.raises(StylecheckFailedError):
            cpp_tester.test_task(*init_task(tmp_path, code))
        check_fail_on_stage(capsys, STAGE_CLANG_TIDY)

    def test_build_error(
            self,
            tmp_path: Path,
            cpp_tester: CppTester,
            capsys: pytest.CaptureFixture[str],
    ) -> None:
        code = 'int Foo() {\n    return 42\n}\n'
        with pytest.raises(BuildFailedError):
            cpp_tester.test_task(*init_task(tmp_path, code))
        check_fail_on_stage(capsys, STAGE_BUILD)

    def test_test_error(
            self,
            tmp_path: Path,
            cpp_tester: CppTester,
            capsys: pytest.CaptureFixture[str],
    ) -> None:
        code = 'int Foo() {\n    return 43;\n}\n'
        with pytest.raises(TestsFailedError):
            cpp_tester.test_task(*init_task(tmp_path, code))
        check_fail_on_stage(capsys, STAGE_TEST)
