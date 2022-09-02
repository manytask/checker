from dataclasses import dataclass
from inspect import cleandoc
from pathlib import Path

import pytest

from checker.utils import create_template_from_gold_solution


def create_file(filename: Path, content: str) -> None:
    with open(filename, 'w') as f:
        content = cleandoc(content)
        f.write(content)


@dataclass
class TemplateTestcase:
    name: str
    code: str
    template: str

    def __repr__(self) -> str:
        return self.name


TEMPLATE_TEST_CASES = [
    TemplateTestcase(
        name='simple',
        code=cleandoc("""
        a = 1
        # TODO: CODE HERE
        b = 2
        # TODO: CODE HERE
        c = 3
        """),
        template=cleandoc("""
        a = 1
        # TODO: CODE HERE
        c = 3
        """),
    ),
    TemplateTestcase(
        name='empty_template',
        code=cleandoc("""
        a = 1
        # TODO: CODE HERE
        # TODO: CODE HERE
        c = 3
        """),
        template=cleandoc("""
        a = 1
        # TODO: CODE HERE
        c = 3
        """),
    ),
    TemplateTestcase(
        name='2_templates',
        code=cleandoc("""
        a = 1
        # TODO: CODE HERE
        b = 2
        # TODO: CODE HERE
        other = 1
        # TODO: CODE HERE
        b = 2
        # TODO: CODE HERE
        c = 3
        """),
        template=cleandoc("""
        a = 1
        # TODO: CODE HERE
        other = 1
        # TODO: CODE HERE
        c = 3
        """),
    ),
    TemplateTestcase(
        name='intentions',
        code=cleandoc("""
        def foo() -> int:
            # TODO: CODE HERE
            a = 1
            # TODO: CODE HERE
            
            with open('f.tmp') as f:
                # TODO: CODE HERE
                f.read()
                # TODO: CODE HERE
        """),
        template=cleandoc("""
        def foo() -> int:
            # TODO: CODE HERE
            
            with open('f.tmp') as f:
                # TODO: CODE HERE
        """),
    ),
]


class TestTemplate:
    @pytest.mark.parametrize('test_case', TEMPLATE_TEST_CASES, ids=repr)
    def test_file_template(self, tmp_path: Path, test_case: TemplateTestcase) -> None:
        tmp_file_code = tmp_path / f'{test_case.name}.py'
        create_file(tmp_file_code, test_case.code)

        create_template_from_gold_solution(tmp_file_code)

        with open(tmp_file_code, 'r') as file:
            content = file.read()

            assert content == cleandoc(test_case.template)

    def test_no_file(self, tmp_path: Path) -> None:
        tmp_file_code = tmp_path / 'this_file_does_not_exist.py'

        with pytest.raises(AssertionError):
            create_template_from_gold_solution(tmp_file_code)

    def test_no_mark(self, tmp_path: Path) -> None:
        CODE = """
        a = 1
        """
        tmp_file_code = tmp_path / 'wrong.py'
        create_file(tmp_file_code, CODE)

        assert not create_template_from_gold_solution(tmp_file_code)
        assert not create_template_from_gold_solution(tmp_file_code, raise_not_found=False)

        with pytest.raises(AssertionError):
            create_template_from_gold_solution(tmp_file_code, raise_not_found=True)

    def test_single_mark(self, tmp_path: Path) -> None:
        CODE = """
        a = 1
        # TODO: CODE HERE
        """
        tmp_file_code = tmp_path / 'wrong.py'
        create_file(tmp_file_code, CODE)

        assert not create_template_from_gold_solution(tmp_file_code)
        assert not create_template_from_gold_solution(tmp_file_code, raise_not_found=False)

        with pytest.raises(AssertionError):
            create_template_from_gold_solution(tmp_file_code, raise_not_found=True)
