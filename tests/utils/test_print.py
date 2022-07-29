import pytest

from checker.utils import print_info, print_task_info


class TestPrint:
    def test_print_info(self, capsys: pytest.CaptureFixture):
        print_info('123')

        captured = capsys.readouterr()
        assert captured.err == '123\n'

    def test_print_task_info(self, capsys: pytest.CaptureFixture):
        print_task_info('123')

        captured = capsys.readouterr()
        assert '123' in captured.err
