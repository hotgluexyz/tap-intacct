"""
API Base class with util functions
"""
import backoff
import datetime as dt
import json
import re
import uuid
from typing import Dict, List, Union, Optional
from urllib.parse import unquote
import copy

import requests
import xmltodict
from xml.parsers.expat import ExpatError

from calendar import monthrange

import singer

from tap_intacct.exceptions import (
    ExpiredTokenError,
    InternalServerError,
    InvalidTokenError,
    NoPrivilegeError,
    NotFoundItemError,
    SageIntacctSDKError,
    WrongParamsError,
    InvalidRequest,
    AuthFailure
)

from http.client import RemoteDisconnected

class PleaseTryAgainLaterError(Exception):
    pass

from .const import GET_BY_DATE_FIELD, INTACCT_OBJECTS, KEY_PROPERTIES, REP_KEYS

logger = singer.get_logger()

class InvalidXmlResponse(Exception):
    pass
class BadGatewayError(Exception):
    pass
class OfflineServiceError(Exception):
    pass
class RateLimitError(Exception):
    pass

def _format_date_for_intacct(datetime: dt.datetime, stream: Optional[str] = None) -> str:
    """
    Intacct expects datetimes in a 'MM/DD/YY HH:MM:SS' string format.
    Args:
        datetime: The datetime to be converted.

    Returns:
        'MM/DD/YY HH:MM:SS' formatted string.
    """
    if stream and stream == "general_ledger_journal_entry_lines":
        return datetime.strftime('%m/%d/%Y')

    return datetime.strftime('%m/%d/%Y %H:%M:%S')


class SageIntacctSDK:
    """The base class for all API classes."""

    def __init__(
        self,
        api_url: str,
        company_id: str,
        sender_id: str,
        sender_password: str,
        user_id: str,
        user_password: str,
        headers: Dict,
    ):
        self.__api_url = api_url
        self.__company_id = company_id
        self.__sender_id = sender_id
        self.__sender_password = sender_password
        self.__user_id = user_id
        self.__user_password = user_password
        self.__headers = headers

        """
        Initialize connection to Sage Intacct
        :param sender_id: Sage Intacct sender id
        :param sender_password: Sage Intacct sender password
        :param user_id: Sage Intacct user id
        :param company_id: Sage Intacct company id
        :param user_password: Sage Intacct user password
        """
        # Initializing variables
        self._set_session_id(
            user_id=self.__user_id,
            company_id=self.__company_id,
            user_password=self.__user_password,
        )

    @backoff.on_exception(
        backoff.expo,
        (
            BadGatewayError,
            OfflineServiceError,
            ConnectionError,
            ConnectionResetError,
            requests.exceptions.ConnectionError,
            requests.exceptions.RequestException,
            InternalServerError,
            RateLimitError,
            RemoteDisconnected,
        ),
        max_tries=8,
        factor=3,
    )
    @singer.utils.ratelimit(10, 1)
    def _set_session_id(self, user_id: str, company_id: str, user_password: str):
        """
        Sets the session id for APIs
        """

        timestamp = dt.datetime.now()
        dict_body = {
            'request': {
                'control': {
                    'senderid': self.__sender_id,
                    'password': self.__sender_password,
                    'controlid': timestamp,
                    'uniqueid': False,
                    'dtdversion': 3.0,
                    'includewhitespace': False,
                },
                'operation': {
                    'authentication': {
                        'login': {
                            'userid': user_id,
                            'companyid': company_id,
                            'password': user_password,
                        }
                    },
                    'content': {
                        'function': {
                            '@controlid': str(uuid.uuid4()),
                            'getAPISession': None,
                        }
                    },
                },
            }
        }

        response = self._post_request(dict_body, self.__api_url)

        if response['authentication']['status'] == 'success':
            session_details = response['result']['data']['api']
            self.__api_url = session_details['endpoint']
            self.__session_id = session_details['sessionid']

        else:
            raise SageIntacctSDKError('Error: {0}'.format(response['errormessage']))
        
    def clean_creds(self, key_field: str, request_body: dict):
        if request_body.get(key_field, {}).get("control", {}):
            for key, _ in request_body[key_field]["control"].items():
                request_body[key_field]["control"][key] = "***"
        
        if request_body.get(key_field, {}).get("operation", {}).get("authentication", {}):
            for key, _ in request_body[key_field]["operation"]["authentication"].items():
                request_body[key_field]["operation"]["authentication"][key] = "***"
        
        return request_body

    def _post_request(self, dict_body: dict, api_url: str) -> Dict:
        """
        Create a HTTP post request.

        Parameters:
            dict_body (dict): HTTP POST body data for the wanted API.
            api_url (str): Url for the wanted API.

        Returns:
            A response from the request (dict).
        """

        api_headers = {'content-type': 'application/xml'}
        api_headers.update(self.__headers)
        body = xmltodict.unparse(dict_body)
        response = requests.post(api_url, headers=api_headers, data=body, timeout=30)

        cleaned_body = self.clean_creds("request", dict_body)

        if not response.ok:
            logger.error(f"Request to {api_url} failed with body: {cleaned_body}")

        if response.status_code == 502:
            raise BadGatewayError(
                f"Response status code: {response.status_code}, response: {response.text}"
            )
        if response.status_code == 503:
            raise OfflineServiceError(
                f"Response status code: {response.status_code}, response: {response.text}"
            )
        if response.status_code == 429:
            raise RateLimitError(
                f"Response status code: {response.status_code}, response: {response.text}"
            )

        try:
            parsed_xml = xmltodict.parse(response.text)
            parsed_response = json.loads(json.dumps(parsed_xml))
        except:
            logger.error(f"Unable to parse response: {response.text}")
            raise InvalidXmlResponse(
                f"Response status code: {response.status_code}, response: {response.text}"
            )
        
        # clean response
        cleaned_response = copy.deepcopy(parsed_response)
        cleaned_response = self.clean_creds("response", cleaned_response)

        if response.status_code == 200:
            if parsed_response['response']['control']['status'] == 'success':
                api_response = parsed_response['response']['operation']

            if parsed_response['response']['control']['status'] == 'failure':
                logger.info(f"Request to {api_url} failed with body: {cleaned_body}")
                exception_msg = self.decode_support_id(
                    parsed_response['response']['errormessage']
                )
                raise WrongParamsError(
                    'Some of the parameters are wrong', exception_msg
                )

            if api_response['authentication']['status'] == 'failure':
                raise InvalidTokenError(
                    'Invalid token / Incorrect credentials',
                    api_response['errormessage'],
                )

            if api_response['result']['status'] == 'success':
                return api_response
            
            logger.error(f"Intacct error response: {cleaned_response}, request body: {cleaned_body}")
            error = api_response.get('result', {}).get('errormessage', {}).get('error', {})
            desc_2 = error.get("description2") if isinstance(error, dict) else error[0].get("description2") if isinstance(error, list) and error else ""

            query_object = (
                dict_body.get("request", {})
                .get("operation", {})
                .get("content", {})
                .get("function", {})
                .get("query", {})
                .get("object")
            )
            if (
                api_response['result']['status'] == 'failure'
                and error
                and "There was an error processing the request" in desc_2
                and query_object == "AUDITHISTORY"
            ):
                return {"result": "skip_and_paginate"}

        exception_msg = parsed_response.get("response", {}).get("errormessage", {}).get("error", {})
        correction = exception_msg.get("correction", {})
        
        logger.info(f"Request to {api_url} failed with response: {cleaned_response}")
        if response.status_code == 400:
            if exception_msg.get("errorno") == "GW-0011":
                raise AuthFailure(f'One or more authentication values are incorrect. Response:{cleaned_response}')
            raise InvalidRequest("Invalid request", cleaned_response)            

        if response.status_code == 401:
            raise InvalidTokenError(
                f'Invalid token / Incorrect credentials. Response: {cleaned_response}'
            )

        if response.status_code == 403:
            raise NoPrivilegeError(
                f'Forbidden, the user has insufficient privilege. Response: {cleaned_response}'
            )

        if response.status_code == 404:
            raise NotFoundItemError(f'Not found item with ID. Response: {cleaned_response}')

        if response.status_code == 498:
            raise ExpiredTokenError(f'Expired token, try to refresh it. Response: {cleaned_response}')

        if response.status_code == 500:
            raise InternalServerError(f'Internal server error. Response: {cleaned_response}')

        if correction and 'Please Try Again Later' in correction:
            raise PleaseTryAgainLaterError(cleaned_response)

        raise SageIntacctSDKError('Error: {0}'.format(cleaned_response))

    def support_id_msg(self, errormessages) -> Union[List, Dict]:
        """
        Finds whether the error messages is list / dict and assign type and error assignment.

        Parameters:
            errormessages (dict / list): error message received from Sage Intacct.

        Returns:
            Error message assignment and type.
        """
        error = {}
        if isinstance(errormessages['error'], list):
            error['error'] = errormessages['error'][0]
            error['type'] = 'list'
        elif isinstance(errormessages['error'], dict):
            error['error'] = errormessages['error']
            error['type'] = 'dict'

        return error

    def decode_support_id(self, errormessages: Union[List, Dict]) -> Union[List, Dict]:
        """
        Decodes Support ID.

        Parameters:
            errormessages (dict / list): error message received from Sage Intacct.

        Returns:
            Same error message with decoded Support ID.
        """
        support_id_msg = self.support_id_msg(errormessages)
        data_type = support_id_msg['type']
        error = support_id_msg['error']
        if error and error.get('description2'):
            message = error['description2']
            support_id = re.search('Support ID: (.*)]', message)
            if support_id and support_id.group(1):
                decoded_support_id = unquote(support_id.group(1))
                message = message.replace(support_id.group(1), decoded_support_id)

        if data_type == 'list':
            errormessages['error'][0]['description2'] = message if message else None
        elif data_type == 'dict':
            errormessages['error']['description2'] = message if message else None

        return errormessages
    

    @backoff.on_exception(
        backoff.expo,
        (
            BadGatewayError,
            OfflineServiceError,
            ConnectionError,
            ConnectionResetError,
            requests.exceptions.ConnectionError,
            requests.exceptions.RequestException,
            InternalServerError,
            RateLimitError,
            RemoteDisconnected,
        ),
        max_tries=8,
        factor=3,
    )
    @singer.utils.ratelimit(10, 1)
    def format_and_send_request(self, data: Dict) -> Union[List, Dict]:
        """
        Format data accordingly to convert them to xml.

        Parameters:
            data (dict): HTTP POST body data for the wanted API.

        Returns:
            A response from the _post_request (dict).
        """

        key = next(iter(data))
        object_type = data[key]['object']
        timestamp = dt.datetime.now()

        dict_body = {
            'request': {
                'control': {
                    'senderid': self.__sender_id,
                    'password': self.__sender_password,
                    'controlid': timestamp,
                    'uniqueid': False,
                    'dtdversion': 3.0,
                    'includewhitespace': False,
                },
                'operation': {
                    'authentication': {'sessionid': self.__session_id},
                    'content': {
                        'function': {'@controlid': str(uuid.uuid4()), key: data[key]}
                    },
                },
            }
        }
        with singer.metrics.http_request_timer(endpoint=object_type):
            response = self._post_request(dict_body, self.__api_url)
        return response['result']


    def get_by_date(
        self, *, object_type: str, fields: List[str], from_date: dt.datetime
    ) -> List[Dict]:
        """
        Get multiple objects of a single type from Sage Intacct, filtered by GET_BY_DATE_FIELD (WHENMODIFIED) date.

        Returns:
            List of Dict in object_type schema.
        """
        # if stream is an audit_history stream filter by object type
        if object_type.startswith("audit_history"):
            filter_table = object_type.split("audit_history_")[-1]
            filter_table_value = INTACCT_OBJECTS[filter_table].lower()
            object_type = "audit_history"   

        intacct_object_type = INTACCT_OBJECTS[object_type]
        total_intacct_objects = []
        pk = KEY_PROPERTIES[object_type][0]
        rep_key = REP_KEYS.get(object_type, GET_BY_DATE_FIELD)


        from_date = from_date + dt.timedelta(seconds=1)
        # if it's an audit_history stream filter only created (C) and deleted (D) records
        if object_type == "audit_history":
            filter = {
                "and":{
                    'greaterthanorequalto': {
                        'field': rep_key,
                        'value': _format_date_for_intacct(from_date),
                    },
                    "equalto":{
                        'field': "OBJECTTYPE",
                        'value': filter_table_value,
                    },
                    "in":{
                        'field': "ACCESSMODE",
                        'value': ["C", "D"],
                    }
                }
            }
        elif object_type == 'budget_details':
            filter = None
        else:
            filter = {
                'greaterthanorequalto': {
                    'field': rep_key,
                    'value': _format_date_for_intacct(from_date, object_type),
                }
            }
            
        get_count = {
            'query': {
                'object': intacct_object_type,
                'select': {'field': pk},
                'pagesize': '1',
                'options': {'showprivate': 'true'},
            }
        }

        if filter:
            get_count["query"]["filter"] = filter
            
        response = self.format_and_send_request(get_count)
        count = int(response['data']['@totalcount'])
        pagesize = 1000
        offset = 0
        while offset < count:

            data = {
                'query': {
                    'object': intacct_object_type,
                    'select': {'field': fields},
                    'options': {'showprivate': 'true'},
                    'pagesize': pagesize,
                    'offset': offset,
                }
            }

            if filter:
                data["query"]["filter"] = filter
            intacct_objects = self.format_and_send_request(data)

            if intacct_objects == "skip_and_paginate" and object_type == "audit_history":
                offset = offset + 99
                continue

            intacct_objects = intacct_objects['data'][
                intacct_object_type
            ]
            # When only 1 object is found, Intacct returns a dict, otherwise it returns a list of dicts.
            if isinstance(intacct_objects, dict):
                intacct_objects = [intacct_objects]

            for record in intacct_objects:
                yield record

            offset = offset + pagesize

    def get_sample(self, intacct_object: str):
        """
        Get a sample of data from an endpoint, useful for determining schemas.
        Returns:
            List of Dict in objects schema.
        """
        data = {
            'readByQuery': {
                'object': intacct_object.upper(),
                'fields': '*',
                'query': None,
                'pagesize': '10',
            }
        }

        return self.format_and_send_request(data)['data'][intacct_object.lower()]

    def get_fields_data_using_schema_name(self, object_type: str):
        """
        Function to fetch fields data for a given object by taking the schema name through
        the API call.This function helps query via the api for any given schema name
        Returns:
            List of Dict in object_type schema.
        """
        intacct_object_type = INTACCT_OBJECTS[object_type]

        # First get the count of object that will be synchronized.
        get_fields = {
            'lookup': {
                'object': intacct_object_type
            }
        }

        response = self.format_and_send_request(get_fields)
        return response

def get_client(
    *,
    api_url: str,
    company_id: str,
    sender_id: str,
    sender_password: str,
    user_id: str,
    user_password: str,
    headers: Dict,
) -> SageIntacctSDK:
    """
    Initializes and returns a SageIntacctSDK object.
    """
    connection = SageIntacctSDK(
        api_url=api_url,
        company_id=company_id,
        sender_id=sender_id,
        sender_password=sender_password,
        user_id=user_id,
        user_password=user_password,
        headers=headers,
    )

    return connection
