from pathlib import Path

from checker.course.driver import CourseDriver


DATA_FOLDER = Path(__file__).parents[1] / 'data' / 'driver'


class TestDriver:
    def test_get_task_dir_name_lectures(self) -> None:
        driver = CourseDriver(Path(''), layout='lectures')
        assert driver.get_task_dir_name('foo/bar') == 'bar'

    def test_get_task_dir_name_groups(self) -> None:
        driver = CourseDriver(Path(''), layout='groups')
        assert driver.get_task_dir_name('foo/bar') == 'bar'

    def test_get_task_dir_name_flat(self) -> None:
        driver = CourseDriver(Path(''), layout='flat')
        assert driver.get_task_dir_name('foo/bar') == 'foo'

    def test_get_task_dir_name_none(self) -> None:
        driver = CourseDriver(Path(''))
        assert driver.get_task_dir_name('foo') is None
