from pathlib import Path

from checker.testers.python import PythonTester


EXAMPLES_FOLDER = Path(__file__).parents[2] / 'examples'


class TestTestersConfigs:

    def test_python_config(self) -> None:
        PythonTester.TaskTestConfig.from_json(EXAMPLES_FOLDER / '.tester.python.json')
