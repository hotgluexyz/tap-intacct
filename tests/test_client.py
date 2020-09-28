import datetime as dt

import pytest

from tap_intacct.client import _format_date_for_intacct, get_client
from tap_intacct.exceptions import SageIntacctSDKError


def test__format_date_for_intacct():
    """
    Ensure that the expected catalog entry is returned in the expected format.
    """
    test_date = dt.datetime(2020, 10, 30, 0, 0, 0)
    actual = _format_date_for_intacct(test_date)
    expected = '10/30/2020 00:00:00'
    assert actual == expected


def test_get_client(mocker):
    post_response = {
        'authentication': {'status': 'success'},
        'result': {
            'data': {'api': {'endpoint': 'test_api_url', 'sessionid': 'test_sessionid'}}
        },
    }
    mocker.patch(
        'tap_intacct.client.SageIntacctSDK._post_request', return_value=post_response
    )
    test_client = get_client(
        api_url='test_api_url',
        company_id='test_company_id',
        sender_id='test_sender_id',
        sender_password='test_sender_password',
        user_id='test_user_id',
        user_password='test_user_password',
        headers={'User-Agent': 'test_user_agent'},
    )

    assert test_client._SageIntacctSDK__api_url == 'test_api_url'
    assert test_client._SageIntacctSDK__session_id == 'test_sessionid'


def test_get_client_auth_error(mocker):
    post_response = {
        'authentication': {'status': 'failure'},
        'errormessage': 'Auth Error',
    }

    mocker.patch(
        'tap_intacct.client.SageIntacctSDK._post_request', return_value=post_response
    )

    with pytest.raises(SageIntacctSDKError):
        get_client(
            api_url='test_api_url',
            company_id='test_company_id',
            sender_id='test_sender_id',
            sender_password='test_sender_password',
            user_id='test_user_id',
            user_password='test_user_password',
            headers={'User-Agent': 'test_user_agent'},
        )
