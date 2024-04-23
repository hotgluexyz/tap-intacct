#!/usr/bin/env python3
import datetime as dt
import json
import ast
import sys
from pathlib import Path
from typing import Dict, FrozenSet, Optional

import singer
from singer import metadata

from tap_intacct.exceptions import SageIntacctSDKError
from tap_intacct.client import SageIntacctSDK, get_client
from tap_intacct.const import DEFAULT_API_URL, KEY_PROPERTIES, REQUIRED_CONFIG_KEYS, INTACCT_OBJECTS, IGNORE_FIELDS, REP_KEYS, GET_BY_DATE_FIELD

logger = singer.get_logger()


class DependencyException(Exception):
    pass


class Context:
    config: dict = {
        'api_url': DEFAULT_API_URL,
        'event_lookback': 1,
    }
    state: dict = {}
    catalog: dict = {}
    stream_map: dict = {}
    counts: dict = {}
    # Client used to access the Intacct API.
    intacct_client: Optional[SageIntacctSDK] = None

    @classmethod
    def get_catalog_entry(cls, stream_name):
        if not cls.stream_map:
            cls.stream_map = {s['tap_stream_id']: s for s in cls.catalog['streams']}
        return cls.stream_map.get(stream_name)

    @classmethod
    def get_selected_fields(cls, stream_name):
        catalog_entry = cls.get_catalog_entry(stream_name)
        columns = []
        for metadata_entry in catalog_entry['metadata']:
            if metadata_entry['breadcrumb']:
                if metadata_entry['metadata']['inclusion'] == 'automatic':
                    columns.append(metadata_entry['breadcrumb'][1])
                elif metadata_entry['metadata']['inclusion'] == 'available':
                    if metadata_entry['metadata'].get('selected'):
                        columns.append(metadata_entry['breadcrumb'][1])
        return columns

    @classmethod
    def get_schema(cls, stream_name):
        stream = [
            s for s in cls.catalog['streams'] if s['tap_stream_id'] == stream_name
        ][0]
        return stream['schema']

    @classmethod
    def is_selected(cls, stream_name):
        stream = cls.get_catalog_entry(stream_name)
        stream_metadata = metadata.to_map(stream['metadata'])
        return metadata.get(stream_metadata, (), 'selected')

    @classmethod
    def print_counts(cls):
        # Separate loops for formatting.
        for stream_name, stream_count in cls.counts.items():
            with singer.metrics.record_counter(stream_name) as counter:
                counter.increment(stream_count)

        logger.info('------------------')
        for stream_name, stream_count in cls.counts.items():
            logger.info(
                '%s: %d records replicated',
                stream_name,
                stream_count,
            )
        logger.info('------------------')


def _get_abs_path(path: str) -> Path:
    p = Path(__file__).parent / path
    return p.resolve()


def _get_start(key: str) -> dt.datetime:
    if key in Context.state:
        start = singer.utils.strptime_to_utc(Context.state[key])

        # commenting logic below due to HGI-5749 
        # # Subtract look-back from Config (default 1 hour) from State, in case of late arriving records.
        # start = start - dt.timedelta(
        #     hours=Context.config['event_lookback']
        # )
    else:
        start = singer.utils.strptime_to_utc(Context.config['start_date'])

    return start


def _get_streams_to_sync() -> FrozenSet[str]:
    return frozenset(
        stream['tap_stream_id']
        for stream in Context.catalog['streams']
        if Context.is_selected(stream['tap_stream_id'])
    )


def _populate_metadata(schema_name: str, schema: Dict) -> Dict:
    """
    Populates initial metadata for each field in a schema.
    Args:
        schema_name: The schema name to generate metadata for e.g. 'general_ledger_accounts'.
        schema: The corresponding JSON schema.

    Returns: Metadata dictionary for the selected stream. Fields are disabled by default.

    """
    mdata = metadata.new()
    mdata = metadata.write(
        mdata, (), 'table-key-properties', KEY_PROPERTIES[schema_name]
    )
    mdata = metadata.write(mdata, (), 'selected', False)

    for field_name in schema['properties']:
        if field_name in KEY_PROPERTIES[schema_name]:
            mdata = metadata.write(
                mdata, ('properties', field_name), 'inclusion', 'automatic'
            )
        else:
            mdata = metadata.write(
                mdata, ('properties', field_name), 'inclusion', 'available'
            )

            mdata = metadata.write(mdata, ('properties', field_name), 'selected', False)

    return mdata





def _load_schema_from_api(stream: str):
    """
    Function to load schema data via an api call for each INTACCT Object to get the fields list for each schema name
    dynamically
    Args:
        stream:

    Returns:
        schema_dict

    """
    Context.intacct_client = get_client(
        api_url=Context.config['api_url'],
        company_id=Context.config['company_id'],
        sender_id=Context.config['sender_id'],
        sender_password=Context.config['sender_password'],
        user_id=Context.config['user_id'],
        user_password=Context.config['user_password'],
        headers={'User-Agent': Context.config['user_agent']}
        if 'user_agent' in Context.config
        else {},
    )
    schema_dict = {}
    schema_dict['type'] = 'object'
    schema_dict['properties'] = {}

    required_list = ["RECORDNO", "WHENMODIFIED"]
    fields_data_response = Context.intacct_client.get_fields_data_using_schema_name(object_type=stream)
    fields_data_list = fields_data_response['data']['Type']['Fields']['Field']
    for rec in fields_data_list:
        if rec['ID'] in IGNORE_FIELDS:
            continue
        if rec['DATATYPE'] in ['PERCENT', 'DECIMAL']:
            type_data_type = 'number'
        elif rec['DATATYPE'] == 'BOOLEAN':
            type_data_type = 'boolean'
        elif rec['DATATYPE'] in ['DATE', 'TIMESTAMP']:
            type_data_type = 'date-time'
        else:
            type_data_type = 'string'
        if type_data_type in ['string', 'boolean', 'number']:
            format_dict = {'type': ["null", type_data_type]}
        else:
            if type_data_type in ['date', 'date-time']:
                format_dict = {'type': ["null", 'string'], 'format': type_data_type}

        schema_dict['properties'][rec['ID']] = format_dict
    schema_dict['required'] = required_list
    return schema_dict


def _load_schemas_from_intact():
    """
    Function to loop through given INTACCT objects list and pass each object as
    a key to load_schema_from_api to inturn get the fields list
    Returns:
   schemas
    """
    schemas = {}
    for key in INTACCT_OBJECTS:
        schemas[key] = _load_schema_from_api(key)
    return schemas

def _load_schemas():
    schemas = {}
    for filename in _get_abs_path('schemas').iterdir():
        stream = filename.stem
        schemas[stream] = _load_schema(stream)
    return schemas


def _transform_and_write_record(
    row: Dict, schema: str, stream: str, time_extracted: dt.datetime
):
    with singer.Transformer() as transformer:
        rec = transformer.transform(
            row,
            schema,
            metadata=metadata.to_map(Context.get_catalog_entry(stream)['metadata']),
        )
    singer.write_record(stream, rec, time_extracted=time_extracted)


def sync_stream(stream: str) -> None:
    """
    Extracts records for the selected stream.
    Args:
        stream: The steam name of the records to be extracted.
    """
    schema = Context.get_schema(stream)

    from_datetime = _get_start(stream)
    time_extracted = singer.utils.now()

    logger.info('Syncing %s data from %s to %s', stream, from_datetime, time_extracted)
    bookmark = from_datetime
    fields = Context.get_selected_fields(stream)

    try:
        # Attempt to get data with all fields
        data = Context.intacct_client.get_by_date(
            object_type=stream,
            fields=fields,
            from_date=from_datetime,
        )

        # Test getting a record
        next(data, None)
    except SageIntacctSDKError as e:
        # Get the error description
        error = ast.literal_eval(e.message[7:])
        result = error['response']['operation']['result']['errormessage']['error']['description2']
        # Trim out the start and end of string message and then convert the neccessary elements into a list
        result = result[70:(result.rfind("[")-1)].replace(" ", "").split(",")

        # Remove any bad fields automatically
        for field in result:
            fields.remove(field)

    # Make the request with the final fiedls
    data = Context.intacct_client.get_by_date(
        object_type=stream,
        fields=fields,
        from_date=from_datetime,
    )

    for intacct_object in data:
        rep_key = REP_KEYS.get(stream, GET_BY_DATE_FIELD)
        row_timestamp = singer.utils.strptime_to_utc(intacct_object[rep_key])
        if row_timestamp > bookmark:
            bookmark = row_timestamp

        _transform_and_write_record(intacct_object, schema, stream, time_extracted)
        Context.counts[stream] += 1

    # Update state
    singer.utils.update_state(Context.state, stream, bookmark)


def do_discover(*, stdout: bool = True) -> Dict:
    """
    Generates a catalog from schemas and loads the schemas from Api call dynamically instead of existing schemas.
    """
    raw_schemas = _load_schemas_from_intact()
    streams = []
    for schema_name, schema in raw_schemas.items():
        # Get metadata for each field
        mdata = _populate_metadata(schema_name, schema)

        # Create and add Catalog entry
        catalog_entry = {
            'stream': schema_name,
            'tap_stream_id': schema_name,
            'schema': schema,
            'metadata': metadata.to_list(mdata),
            'key_properties': KEY_PROPERTIES[schema_name],
        }
        streams.append(catalog_entry)

    catalog = {'streams': streams}

    if stdout:
        # Dump catalog to stdout
        json.dump(catalog, sys.stdout, indent=4)

    return catalog


def do_sync() -> None:
    """
    Syncs all streams selected in Context.catalog.
    Writes out state file for events stream once sync completed.
    """
    selected_stream_ids = _get_streams_to_sync()

    logger.info(
        'Starting sync. Will sync these streams: \n%s',
        '\n'.join(selected_stream_ids),
    )
    for stream in selected_stream_ids:
        singer.write_schema(stream, Context.get_schema(stream), KEY_PROPERTIES[stream])
        Context.counts[stream] = 0
        sync_stream(stream)

    singer.write_state(Context.state)
    logger.info('Sync completed')


@singer.utils.handle_top_exception(logger)
def main() -> None:
    args = singer.utils.parse_args(REQUIRED_CONFIG_KEYS)
    Context.config.update(args.config)

    if args.state:
        Context.state.update(args.state)

    if args.discover:
        do_discover()
    else:
        Context.catalog.update(
            args.catalog.to_dict() if args.catalog else do_discover(stdout=False)
        )

        Context.intacct_client = get_client(
            api_url=Context.config['api_url'],
            company_id=Context.config['company_id'],
            sender_id=Context.config['sender_id'],
            sender_password=Context.config['sender_password'],
            user_id=Context.config['user_id'],
            user_password=Context.config['user_password'],
            headers={'User-Agent': Context.config['user_agent']}
            if 'user_agent' in Context.config
            else {},
        )

        do_sync()
        Context.print_counts()


if __name__ == '__main__':
    main()
