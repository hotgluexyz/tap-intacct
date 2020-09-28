import pytest

from tap_intacct import Context
from tap_intacct.client import get_client
from tap_intacct.const import DEFAULT_API_URL


@pytest.fixture(name='mock_context')
def _mock_context(mocker):
    return mocker.patch('tap_intacct.Context', autospec=True)


@pytest.fixture(name='clean_context')
def _clean_context():
    class CleanContext(Context):
        config = {}
        state = {}
        catalog = {}
        stream_map = {}
        counts = {}
        intacct_client = None

    return CleanContext


@pytest.fixture(name='intacct_client')
def _intacct_client(mocker):
    mocker.patch(
        'tap_intacct.get_client.SageIntacctSDK.__init__._set_session_id',
    )
    return get_client(
        api_url=DEFAULT_API_URL,
        company_id='test_company_id',
        sender_id='test_sender_id',
        sender_password='test_sender_password',
        user_id='test_user_id',
        user_password='test_user_password',
        headers={'content-type': 'application/xml'},
    )


@pytest.fixture(name='mock_response_json')
def _mock_response_json():
    return {
        'items': [
            {
                'address': 'alice@example.com',
                'tag': '*',
                'created_at': 'Fri, 21 Oct 2011 11:02:55 GMT',
            },
            {
                'address': 'alice@example.com',
                'tag': '*',
                'created_at': 'Fri, 21 Oct 2011 11:02:55 GMT',
            },
            {
                'address': 'alice@example.com',
                'tag': '*',
                'created_at': 'Fri, 21 Oct 2011 11:02:55 GMT',
            },
        ],
        'paging': {
            'first': 'https://api.mailgun.net/v3/first',
            'next': 'https://api.mailgun.net/v3/next',
            'previous': 'https://api.mailgun.net/v3/previous',
            'last': 'https://api.mailgun.net/v3/last',
        },
    }


@pytest.fixture(name='mock_empty_response_json')
def _mock_empty_response_json():
    return {"items": []}


@pytest.fixture(name='mock_schema')
def _mock_schema():
    return {
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'created_at': {'type': 'string', 'format': 'date-time'},
            'test_field_1': {'type': 'number'},
            'test_field_2': {'type': 'number'},
        },
        'required': ['id', 'created_at'],
    }


@pytest.fixture(name='mock_catalog')
def _mock_catalog():
    return {
        'streams': [
            {
                'stream': 'test_stream',
                'tap_stream_id': 'test_stream',
                'schema': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'string'},
                        'created_at': {'type': 'string', 'format': 'date-time'},
                        'test_field_1': {'type': 'number'},
                        'test_field_2': {'type': 'number'},
                    },
                    'required': ['id', 'created_at'],
                },
                'metadata': [
                    {
                        'breadcrumb': (),
                        'metadata': {
                            'table-key-properties': [
                                'id',
                                'created_at',
                            ],
                            'selected': True,
                        },
                    },
                    {
                        'breadcrumb': ('properties', 'id'),
                        'metadata': {'inclusion': 'automatic'},
                    },
                    {
                        'breadcrumb': ('properties', 'created_at'),
                        'metadata': {'inclusion': 'automatic'},
                    },
                    {
                        'breadcrumb': ('properties', 'test_field_1'),
                        'metadata': {
                            'inclusion': 'available',
                            'selected': True,
                        },
                    },
                    {
                        'breadcrumb': ('properties', 'test_field_2'),
                        'metadata': {
                            'inclusion': 'available',
                            'selected': False,
                        },
                    },
                ],
                'key_properties': ['id', 'created_at'],
            }
        ]
    }


@pytest.fixture(name='mock_state')
def _mock_state():
    return {'events': '2020-01-01T00:00:00.000000Z'}


@pytest.fixture(name='mock_config')
def _mock_config():
    return {'start_date': '2020-01-01T00:00:00.000000Z'}
