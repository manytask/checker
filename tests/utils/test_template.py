from __future__ import annotations

from dataclasses import dataclass
from inspect import cleandoc
from pathlib import Path

import pytest

from checker.utils import create_template_from_gold_solution, cut_marked_code_from_string


def create_file(filename: Path, content: str) -> None:
    with open(filename, 'w') as f:
        content = cleandoc(content)
        f.write(content)


@dataclass
class TemplateTestcase:
    name: str
    code: str
    template: str
    start_end: str | tuple[str, str] = ('TODO: CODE HERE', 'TODO: CODE HERE')
    replace: str = 'TODO: CODE HERE'

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
        start_end=('TODO: CODE HERE', 'TODO: CODE HERE'),
        replace='TODO: CODE HERE',
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
        start_end='TODO: CODE HERE',
        replace='TODO: CODE HERE',
    ),
    TemplateTestcase(
        name='different_strings',
        code=cleandoc("""
        a = 1
        # SOLUTION START
        b = 2
        # SOLUTION END
        c = 3
        """),
        template=cleandoc("""
        a = 1
        # TODO: CODE HERE
        c = 3
        """),
        start_end=('# SOLUTION START', '# SOLUTION END'),
        replace='# TODO: CODE HERE',
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
        start_end='TODO: CODE HERE',
        replace='TODO: CODE HERE',
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
        start_end='TODO: CODE HERE',
        replace='TODO: CODE HERE',
    ),
    TemplateTestcase(
        name='complex_intentions',
        code=cleandoc("""
        import os
        
        class A:
            def foo(self) -> int:
                # TODO: CODE HERE
                return 1
                # TODO: CODE HERE
            
            def bar(self) -> int:
                return 2
        
        if __name__ == '__main__':
            # TODO: CODE HERE
            a = A()
            print(a.foo())
            # TODO: CODE HERE
        """),
        template=cleandoc("""
        import os
        
        class A:
            def foo(self) -> int:
                # TODO: CODE HERE
            
            def bar(self) -> int:
                return 2
        
        if __name__ == '__main__':
            # TODO: CODE HERE
        """),
        start_end='TODO: CODE HERE',
        replace='TODO: CODE HERE',
    ),
    TemplateTestcase(
        name='cpp_hello_world',
        code=cleandoc("""
        #include <iostream>
        
        int main() {
            // TODO: CODE HERE
            std::cout << "Hello World!";
            // TODO: CODE HERE
            return 0;
        }
        """),
        template=cleandoc("""
        #include <iostream>
        
        int main() {
            // TODO: CODE HERE
            return 0;
        }
        """),
        start_end='TODO: CODE HERE',
        replace='TODO: CODE HERE',
    ),
]


class TestTemplate:
    @pytest.mark.parametrize('test_case', TEMPLATE_TEST_CASES, ids=repr)
    def test_cut_marked_code(self, test_case: TemplateTestcase) -> None:
        template = cut_marked_code_from_string(
            content=test_case.code,
            clear_mark=test_case.start_end,
            clear_mark_replace=test_case.replace,
            raise_not_found=False,
        )
        assert template == test_case.template

    def test_cut_marked_code_wrong(self) -> None:
        CODE = cleandoc("""
        a = 1
        # Start string
        b = 2
        # Start string
        c = 3 
        """)
        assert cut_marked_code_from_string(
            content=CODE,
            clear_mark=('Start string', 'End string'),
            clear_mark_replace='Start string',
            raise_not_found=False,
        ) == CODE
        with pytest.raises(AssertionError):
            cut_marked_code_from_string(
                content=CODE,
                clear_mark=('Start string', 'End string'),
                clear_mark_replace='Start string',
                raise_not_found=True,
            )

    def test_file_template(self, tmp_path: Path) -> None:
        test_case = TEMPLATE_TEST_CASES[0]

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

        assert not create_template_from_gold_solution(tmp_file_code, raise_not_found=False)

        with pytest.raises(AssertionError):
            create_template_from_gold_solution(tmp_file_code, raise_not_found=True)
