from __future__ import annotations

from datetime import datetime
from tempfile import TemporaryDirectory, NamedTemporaryFile
from typing import Any
from unittest import mock
from os.path import basename

import pytest
from pydantic import ValidationError

from checker.plugins.manytask import ManytaskPlugin


class TestManytaskPlugin:
    @staticmethod
    def get_sample_args() -> ManytaskPlugin.Args:
        return ManytaskPlugin.Args(username='user1',
                                   task_name='task1',
                                   score=0.5,
                                   report_url='https://example.com',
                                   tester_token='token1',
                                   check_deadline=True)

    @pytest.mark.parametrize(
        "parameters, expected_exception",
        [
            ({
                 'username': 'user1',
                 'task_name': 'task1',
                 'score': 0.5,
                 'report_url': 'https://example.com',
                 'tester_token': 'token1',
                 'check_deadline': True,
             }, None),
            ({
                 'origin': 'test/',
                 'patterns': ['*.py'],
                 'username': 'user2',
                 'task_name': 'task2',
                 'score': 0.01,
                 'report_url': 'https://example2.com',
                 'tester_token': 'token2',
                 'check_deadline': True,
                 'send_time': datetime.now()
             }, None),
            ({
                 'origin': '/test/test/test',
                 'patterns': ['*.py', '**.*', 'test'],
                 'username': 'user3',
                 'task_name': 'task3',
                 'score': 1.,
                 'report_url': 'https://example3.com',
                 'tester_token': 'token3',
                 'check_deadline': True,
                 'send_time': '2023-12-21T00:52:36.166028+06:00'
             }, None),
            ({
                 'origin': './',
                 'patterns': [],
                 'username': 'user4',
                 'task_name': 'task4',
                 'score': 1.5,
                 'report_url': 'https://example4.com',
                 'tester_token': 'token4',
                 'check_deadline': False
             }, None),
            ({
                 'origin': 'test/',
                 'patterns': ['*.py'],
                 'username': 'user2',
                 'task_name': 'task2',
                 'score': 0.01,
                 'report_url': 'invalidurl',
                 'tester_token': 'token2',
                 'check_deadline': True,
                 'send_time': datetime.now()
             }, ValidationError),
            ({
                 'origin': 'test/',
                 'patterns': ['*.py'],
                 'username': 'user2',
                 'task_name': 'task2',
                 'score': 0.01,
                 'report_url': 'https://example2.com',
                 'tester_token': 'token2',
                 'check_deadline': True,
                 'send_time': 'invalidtime'
             }, ValidationError),
            ({}, ValidationError),
        ],
    )
    def test_plugin_args(
            self, parameters: dict[str, Any], expected_exception: Exception | None
    ) -> None:
        if expected_exception:
            with pytest.raises(expected_exception):
                ManytaskPlugin.Args(**parameters)
        else:
            ManytaskPlugin.Args(**parameters)

    @pytest.mark.parametrize(
        "extensions_to_create, patterns_to_take, taken_files_num",
        [
            (['.py', '.yml', '.txt'],
             ['*'],
             3),
            (['.py', '.yml', '.txt'],
             ['*.py'],
             1),
            (['.py', '.yml', '.py', '.yml', '.txt'],
             ['*.py', '*.yml'],
             4),
            (['.py', '.yml', '.txt'],
             ['*.not'],
             0)
        ]
    )
    def test_collect_files_to_send(self, patterns_to_take: list[str], extensions_to_create: list[str],
                                   taken_files_num: int) -> None:
        args = self.get_sample_args()
        args.patterns = patterns_to_take

        with TemporaryDirectory() as tdir:
            args.origin = tdir
            tempfiles = []
            expected_filenames = []

            for extension in extensions_to_create:
                ntfile = NamedTemporaryFile(dir=tdir, suffix=extension)
                tempfiles.append(ntfile)
                if f'*{extension}' in patterns_to_take or '*' in patterns_to_take:
                    expected_filenames.append(basename(tempfiles[-1].name))

            with mock.patch("builtins.open", mock.mock_open(read_data=b"File content")) as mock_open_file:
                result = ManytaskPlugin._collect_files_to_send(args)

                assert result is not None, 'Didn\'t collect files'
                assert len(result) == taken_files_num, 'Wrong file quantity are collected'
                assert sorted(result.keys()) == sorted(expected_filenames), 'Wrong files are collected'

                if taken_files_num:
                    mock_open_file.assert_called_with(mock.ANY, "rb")
