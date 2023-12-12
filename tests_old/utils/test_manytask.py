from __future__ import annotations

import datetime

import pytest
from pytest_mock import MockFixture

from checker_old.exceptions import GetFailedError, PushFailedError
from checker_old.utils import get_score, push_report


BASE_URL = 'https://test.manytask.org'
TESTER_TOKEN = 'test_token'
TEST_NOW_DATETIME = datetime.datetime(2021, 1, 1, 0, 0, 0)
TEST_DEADLINE_DATETIME = TEST_NOW_DATETIME + datetime.timedelta(hours=1)
TEST_TASK_NAME = 'some_task'
TEST_USER_ID = 1
TEST_USERNAME = 'username'
TEST_SCORE = 40.0


@pytest.fixture
def mock_report_request(mocker: MockFixture) -> MockFixture:
    def mock_side_effect(*args, **kwargs):
        url = args[0] if len(args) > 0 else kwargs.get('url', '')
        data = args[1] if len(args) > 1 else kwargs.get('data', dict())
        files = kwargs.get('files', dict())

        if (
                url != f'{BASE_URL}/api/report' or
                data.get('token', None) != TESTER_TOKEN or
                data.get('task', None) != TEST_TASK_NAME or
                data.get('user_id', None) != TEST_USER_ID
        ):
            mock_response = mocker.Mock()
            mock_response.status_code = 400
            mock_response.text = 'Some error'
            return mock_response

        commit_time = data.get('commit_time', None)
        submit_time = commit_time + datetime.timedelta(minutes=5) if commit_time is not None else None

        mock_response = mocker.Mock()
        mock_response.json.return_value = {
            'username': TEST_USERNAME,
            'commit_time': commit_time,
            'submit_time': submit_time,
            'demand_multiplier': 1,
            'score': 0.0 if data.get('check_deadline', True) and commit_time > TEST_DEADLINE_DATETIME else TEST_SCORE,
        }
        mock_response.status_code = 200
        return mock_response


    mock = mocker.patch('requests.post')
    mock.side_effect = mock_side_effect
    return mock


class TestPushReport:

    def test_simple(self, mock_report_request: MockFixture) -> None:
        username, score, result_commit_time, result_submit_time, demand_multiplier = push_report(
            report_base_url=BASE_URL,
            tester_token=TESTER_TOKEN,
            task_name=TEST_TASK_NAME,
            user_id=TEST_USER_ID,
            score=TEST_SCORE,
            files=None,
            send_time=TEST_NOW_DATETIME,
            check_deadline=True,
            use_demand_multiplier=False,
        )
        assert username == TEST_USERNAME
        assert score == TEST_SCORE
        assert result_commit_time == TEST_NOW_DATETIME
        assert result_submit_time > TEST_NOW_DATETIME
        assert demand_multiplier == 1.0

        mock_report_request.assert_called_once()

    @pytest.mark.parametrize('check_deadline', [True, False])
    def test_check_deadline(self, mock_report_request: MockFixture, check_deadline: bool) -> None:
        username, score, result_commit_time, result_submit_time, demand_multiplier = push_report(
            report_base_url=BASE_URL,
            tester_token=TESTER_TOKEN,
            task_name=TEST_TASK_NAME,
            user_id=TEST_USER_ID,
            score=TEST_SCORE,
            send_time=TEST_DEADLINE_DATETIME + datetime.timedelta(days=1),
            check_deadline=check_deadline,
            use_demand_multiplier=False,
        )

        if check_deadline:
            assert score == 0.0
        else:
            assert score == TEST_SCORE

    def test_wrong_tester_token(self, mock_report_request: MockFixture) -> None:
        with pytest.raises(PushFailedError):
            push_report(
                report_base_url=BASE_URL,
                tester_token='wrong_token',
                task_name=TEST_TASK_NAME,
                user_id=TEST_USER_ID,
                score=TEST_SCORE,
                send_time=TEST_NOW_DATETIME,
            )

    def test_wrong_task_name(self, mock_report_request: MockFixture) -> None:
        with pytest.raises(PushFailedError):
            push_report(
                report_base_url=BASE_URL,
                tester_token=TESTER_TOKEN,
                task_name='wrong_task_name',
                user_id=TEST_USER_ID,
                score=TEST_SCORE,
                send_time=TEST_NOW_DATETIME,
            )

    def test_wrong_user_id(self, mock_report_request: MockFixture) -> None:
        with pytest.raises(PushFailedError):
            push_report(
                report_base_url=BASE_URL,
                tester_token=TESTER_TOKEN,
                task_name=TEST_TASK_NAME,
                user_id=1000,
                score=TEST_SCORE,
                send_time=TEST_NOW_DATETIME,
            )


@pytest.fixture
def mock_score_request(mocker: MockFixture) -> MockFixture:
    def mock_side_effect(*args, **kwargs):
        url = args[0] if len(args) > 0 else kwargs.get('url', '')
        data = args[1] if len(args) > 1 else kwargs.get('data', dict())

        if (
                url != f'{BASE_URL}/api/score' or
                data.get('token', None) != TESTER_TOKEN or
                data.get('user_id', None) != TEST_USER_ID
        ):
            mock_response = mocker.Mock()
            mock_response.status_code = 400
            mock_response.text = 'Some error'
            return mock_response

        mock_response = mocker.Mock()
        mock_response.json.return_value = {
            'score': TEST_SCORE if data.get('task') == TEST_TASK_NAME else None,
        }
        mock_response.status_code = 200
        return mock_response


    mock = mocker.patch('requests.get')
    mock.side_effect = mock_side_effect
    return mock


class TestGetScore:

    def test_simple(self, mock_score_request: MockFixture) -> None:
        score = get_score(
            report_base_url=BASE_URL,
            tester_token=TESTER_TOKEN,
            task_name=TEST_TASK_NAME,
            user_id=TEST_USER_ID,
        )
        assert score == TEST_SCORE

        mock_score_request.assert_called_once()

    def test_wrong_user_id(self, mock_score_request: MockFixture) -> None:
        with pytest.raises(GetFailedError):
            get_score(
                report_base_url=BASE_URL,
                tester_token=TESTER_TOKEN,
                task_name=TEST_TASK_NAME,
                user_id=1000,
            )

    def test_wrong_task_name(self, mock_score_request: MockFixture) -> None:
        score = get_score(
            report_base_url=BASE_URL,
            tester_token=TESTER_TOKEN,
            task_name='wrong_task_name',
            user_id=TEST_USER_ID,
        )

        assert score is None

    def test_wrong_tester_token(self, mock_score_request: MockFixture) -> None:
        with pytest.raises(GetFailedError):
            get_score(
                report_base_url=BASE_URL,
                tester_token='wrong_token',
                task_name=TEST_TASK_NAME,
                user_id=TEST_USER_ID,
            )
