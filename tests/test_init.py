import argparse
import datetime as dt
from unittest.mock import call

from singer.catalog import Catalog

import tap_intacct


def test_context_get_catalog_entry(clean_context, mock_catalog):
    """
    Ensure that the expected catalog entry is returned in the expected format.
    """
    clean_context.catalog = mock_catalog
    expected = mock_catalog['streams'][0]
    actual = clean_context.get_catalog_entry('test_stream')
    assert expected == actual


def test_context_is_selected(clean_context, mock_catalog):
    """
    Ensure that the correct response is received if the stream is selected in the catalog.
    """
    clean_context.catalog = mock_catalog
    expected = True
    actual = clean_context.is_selected('test_stream')
    assert expected == actual


def test_context_is_not_selected(clean_context, mock_catalog):
    """
    Ensure that the correct response is received if the stream is selected in the catalog.
    """
    mutated_mock_catalog = mock_catalog
    mutated_mock_catalog['streams'][0]['metadata'][0]['metadata']['selected'] = False
    clean_context.catalog = mutated_mock_catalog
    expected = False
    actual = clean_context.is_selected('test_stream')
    assert expected == actual


def test_context_get_schema(clean_context, mock_catalog, mock_schema):
    """
    Ensure that the expected schema is returned in the expected format.
    """
    clean_context.catalog = mock_catalog
    expected = mock_schema
    actual = clean_context.get_schema('test_stream')
    assert expected == actual


def test_sync_stream(mocker, mock_schema, mock_context):
    """
    Ensure that the expected methods are called based on the returned response from the endpoint.
    """
    mock_context.is_selected.return_value = True
    mock_context.get_schema.return_value = mock_schema
    mock_context.intacct_client.get_by_date.return_value = [
        {
            'RECORDNO': '885',
            'PROJECTID': 'FMY/21/026',
            'WHENMODIFIED': '02/20/2018 12:11:43',
        },
        {
            'RECORDNO': '887',
            'PROJECTID': 'FMY/20/254',
            'WHENMODIFIED': '02/21/2020 07:36:59',
        },
        {
            'RECORDNO': '888',
            'PROJECTID': 'FMY/21/027',
            'WHENMODIFIED': '02/21/2020 08:00:10',
        },
    ]

    mock_get_start = mocker.patch(
        'tap_intacct._get_start',
        return_value=dt.datetime(2019, 12, 31, 23, 0, tzinfo=dt.timezone.utc),
    )
    mock_get_now = mocker.patch(
        'tap_intacct.singer.utils.now',
        return_value=dt.datetime(2020, 8, 12, 17, 43, tzinfo=dt.timezone.utc),
    )
    mock_transform = mocker.patch(
        'tap_intacct._transform_and_write_record', autospec=True
    )
    mock_update_state = mocker.patch(
        'tap_intacct.singer.utils.update_state', autospec=True
    )

    tap_intacct.sync_stream('test_stream')

    mock_get_start.assert_called_once()
    mock_get_now.assert_called_once()
    assert mock_transform.call_count == 3
    mock_update_state.assert_called_once()


def test_get_start_no_state(mock_context):
    """
    Ensure that the expected value is returned from the _get_start function when no state is present.
    """
    mock_context.config = {'start_date': '2019-01-01T00:00:00.000000Z'}
    expected = dt.datetime(2019, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
    actual = tap_intacct._get_start('events')

    assert expected == actual


def test_get_start_state(mock_state, mock_context):
    """
    Ensure that the expected value is returned from the _get_start function when a state is present.
    """
    mock_context.config = {'event_lookback': 1}
    mock_context.state = mock_state

    expected = dt.datetime(2019, 12, 31, 23, 0, tzinfo=dt.timezone.utc)
    actual = tap_intacct._get_start('events')

    assert expected == actual


def test_get_selected_fields(clean_context, mock_catalog):
    """
    Ensure that the catalog is read properly and the expected fields are returned by get_selected_fields.
    """
    clean_context.catalog = mock_catalog

    expected = ['id', 'created_at', 'test_field_1']
    actual = clean_context.get_selected_fields('test_stream')

    assert expected == actual


def test_get_streams_to_sync(mock_catalog, mock_context):
    """
    Ensure that the catalog is read properly and the expected selected streams are returned by _get_streams_to_sync.
    """
    mock_context.catalog = mock_catalog

    expected = frozenset(['test_stream'])
    actual = tap_intacct._get_streams_to_sync()

    assert expected == actual


def test_populate_metadata(mocker, mock_schema):
    """
    Ensure that metadata is populated as expected...
    - Key properties are applied
    - Fields are not selected by default.
    """
    mocker.patch.dict(
        'tap_intacct.KEY_PROPERTIES',
        {'test_schema': ['id', 'created_at']},
    )

    expected = {
        (): {
            'table-key-properties': ['id', 'created_at'],
            'selected': False,
        },
        ('properties', 'id'): {'inclusion': 'automatic'},
        ('properties', 'created_at'): {'inclusion': 'automatic'},
        ('properties', 'test_field_1'): {
            'inclusion': 'available',
            'selected': False,
        },
        ('properties', 'test_field_2'): {
            'inclusion': 'available',
            'selected': False,
        },
    }

    actual = tap_intacct._populate_metadata(
        schema_name='test_schema', schema=mock_schema
    )

    assert expected == actual


def test_transform_and_write_record(capfd, mocker, mock_schema, mock_catalog):
    """
    Ensure that stdout from the _transform_and_write_record function is expected.
    """
    stream = 'test_stream'
    record = {
        'id': 'test_id',
        'created_at': '2020-07-29T14:27:29.000000Z',
        'test_field_1': 1,
        'test_field_2': 2,
    }
    mocker.patch(
        'tap_intacct.Context.get_catalog_entry',
        return_value=mock_catalog['streams'][0],
    )

    tap_intacct._transform_and_write_record(
        record,
        mock_schema,
        stream,
        time_extracted=dt.datetime(2019, 12, 31, 23, 0, tzinfo=dt.timezone.utc),
    )

    expected_stdout = (
        '{"type": "RECORD", "stream": "test_stream", "record": {"id": "test_id", "created_at": '
        '"2020-07-29T14:27:29.000000Z", "test_field_1": 1.0}, "time_extracted": "2019-12-31T23:00:00.000000Z"}\n'
    )
    actual_stdout = capfd.readouterr().out

    assert expected_stdout == actual_stdout


# def test_sync_domains(mocker, mock_schema, mock_context):
#     """
#     Ensure that the expected functions are called during sync_domains.
#     """
#     mock_context.get_schema.return_value = mock_schema
#     mock_context.intacct_client.get_domains.return_value = [
#         {'id': 'id1', 'name': 'domain1', 'created_at': '2020-07-29T14:27:29.000000Z'},
#         {'id': 'id2', 'name': 'domain2', 'created_at': '2020-07-29T14:27:29.000000Z'},
#         {'id': 'id3', 'name': 'domain3', 'created_at': '2020-07-29T14:27:29.000000Z'},
#         {'id': 'id4', 'name': 'domain4', 'created_at': '2020-07-29T14:27:29.000000Z'},
#     ]
#     mock_transform = mocker.patch(
#         'tap_intacct._transform_and_write_record', autospec=True
#     )
#
#     tap_intacct.sync_domains()
#
#     mock_context.get_schema.assert_called_once_with('domains')
#     mock_context.intacct_client.get_domains.assert_called_once()
#     assert mock_transform.call_count == 4


def test_do_discover(mocker, mock_schema, mock_catalog, capfd):
    """
    Ensure that the stdout and return value of do_discover is as expected.
    """
    mocker.patch(
        'tap_intacct._load_schemas',
        return_value={
            'test_stream': mock_schema,
        },
    )
    mocker.patch.dict(
        'tap_intacct.KEY_PROPERTIES',
        {'test_stream': ['id', 'created_at']},
    )

    return_value = tap_intacct.do_discover()

    stdout = capfd.readouterr().out

    assert '"stream": "test_stream"' in stdout
    for metadata_entry in return_value['streams'][0]['metadata']:
        assert metadata_entry['metadata'].get('selected') is not True


def test_main_discover(mocker, mock_config, mock_context):
    """
    Ensure that the correct functions are called when tap is executed in discovery mode.
    """
    mocker.patch(
        'tap_intacct.singer.utils.parse_args',
        return_value=argparse.Namespace(config=mock_config, discover=True, state=None),
    )
    mock_do_discover = mocker.patch('tap_intacct.do_discover', autospec=True)

    tap_intacct.main()

    mock_context.config.update.assert_called_once_with(mock_config)
    mock_context.state.update.assert_not_called()
    mock_do_discover.assert_called_once()


def test_main_no_state(mocker, mock_catalog, mock_config, mock_context):
    """
    Ensure that the correct functions are called when tap is executed with no state.
    """
    catalog = Catalog.from_dict(mock_catalog)

    mocker.patch(
        'tap_intacct.singer.utils.parse_args',
        return_value=argparse.Namespace(
            catalog=catalog,
            config=mock_config,
            state=None,
            discover=None,
        ),
    )

    mock_get_client = mocker.patch('tap_intacct.get_client', autospec=True)
    mock_do_sync = mocker.patch('tap_intacct.do_sync', autospec=True)

    tap_intacct.main()

    mock_context.config.update.assert_called_once_with(mock_config)
    mock_context.state.update.assert_not_called()
    mock_context.catalog.update.assert_called_once_with(catalog.to_dict())
    mock_get_client.assert_called_once()
    mock_do_sync.assert_called_once()
    mock_context.print_counts.assert_called_once()


def test_main_with_state(mocker, mock_config, mock_catalog, mock_state, mock_context):
    """
    Ensure that the correct functions are called when tap is executed with a state file.
    """
    catalog = Catalog.from_dict(mock_catalog)

    mocker.patch(
        'tap_intacct.singer.utils.parse_args',
        return_value=argparse.Namespace(
            config=mock_config,
            state=mock_state,
            catalog=catalog,
            discover=False,
        ),
    )
    mock_get_client = mocker.patch('tap_intacct.get_client', autospec=True)
    mock_do_sync = mocker.patch('tap_intacct.do_sync', autospec=True)

    tap_intacct.main()

    mock_context.config.update.assert_called_once_with(mock_config)
    mock_context.state.update.assert_called_once_with(mock_state)
    mock_context.catalog.update.assert_called_once_with(catalog.to_dict())
    mock_get_client.assert_called_once()
    mock_do_sync.assert_called_once()
    mock_context.print_counts.assert_called_once()


def test_do_sync(mocker, mock_state, mock_context):
    """
    Ensure that the correct functions are called when tap is executed in sync mode.
    """
    streams = frozenset(['projects', 'general_ledger_accounts'])

    mock_context.get_schema.return_value = 'schema'
    mock_context.is_selected.return_value = True
    mock_context.state = mock_state

    mock__get_streams_to_sync = mocker.patch(
        'tap_intacct._get_streams_to_sync', return_value=streams, autospec=True
    )

    mocker.patch('tap_intacct.singer.write_schema', autospec=True)

    mock_sync_stream = mocker.patch('tap_intacct.sync_stream', autospec=True)

    mock_singer_write_state = mocker.patch(
        'tap_intacct.singer.write_state', autospec=True
    )

    tap_intacct.do_sync()

    mock__get_streams_to_sync.assert_called_once()

    assert mock_sync_stream.call_count == 2
    mock_sync_stream.assert_has_calls(
        [call('projects'), call('general_ledger_accounts')], any_order=True
    )

    mock_singer_write_state.assert_called_once_with(mock_state)
