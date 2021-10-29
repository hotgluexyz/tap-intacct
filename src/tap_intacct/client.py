"""
API Base class with util functions
"""
import datetime as dt
import json
import re
import uuid
from typing import Dict, List, Union
from urllib.parse import unquote

import requests
import xmltodict

import singer

from tap_intacct.exceptions import (
    ExpiredTokenError,
    InternalServerError,
    InvalidTokenError,
    NoPrivilegeError,
    NotFoundItemError,
    SageIntacctSDKError,
    WrongParamsError,
)

from .const import GET_BY_DATE_FIELD, INTACCT_OBJECTS, INTACCT_OBJECTS_WITH_CHILD_DATA
logger = singer.get_logger()

def _format_date_for_intacct(datetime: dt.datetime) -> str:
    """
    Intacct expects datetimes in a 'MM/DD/YY HH:MM:SS' string format.
    Args:
        datetime: The datetime to be converted.

    Returns:
        'MM/DD/YY HH:MM:SS' formatted string.
    """
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

    @singer.utils.ratelimit(10, 1)
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
        response = requests.post(api_url, headers=api_headers, data=body)

        parsed_xml = xmltodict.parse(response.text)
        parsed_response = json.loads(json.dumps(parsed_xml))

        if response.status_code == 200:
            if parsed_response['response']['control']['status'] == 'success':
                api_response = parsed_response['response']['operation']

            if parsed_response['response']['control']['status'] == 'failure':
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

        if response.status_code == 400:
            raise WrongParamsError('Some of the parameters are wrong', parsed_response)

        if response.status_code == 401:
            raise InvalidTokenError(
                'Invalid token / Incorrect credentials', parsed_response
            )

        if response.status_code == 403:
            raise NoPrivilegeError(
                'Forbidden, the user has insufficient privilege', parsed_response
            )

        if response.status_code == 404:
            raise NotFoundItemError('Not found item with ID', parsed_response)

        if response.status_code == 498:
            raise ExpiredTokenError('Expired token, try to refresh it', parsed_response)

        if response.status_code == 500:
            raise InternalServerError('Internal server error', parsed_response)

        raise SageIntacctSDKError('Error: {0}'.format(parsed_response))

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
        if error and error['description2']:
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

        if object_type in INTACCT_OBJECTS_WITH_CHILD_DATA:
            return self.get_by_date_and_load_child_data(
                object_type=object_type,
                fields=fields,
                from_date=from_date
            )
        else:
            return self.get_by_date_no_child_data(
                object_type=object_type,
                fields=fields,
                from_date=from_date
            )

    def get_by_date_no_child_data(
        self, *, object_type: str, fields: List[str], from_date: dt.datetime
    ) -> List[Dict]:
        """
        Get multiple objects of a single type from Sage Intacct, filtered by GET_BY_DATE_FIELD (WHENMODIFIED) date.

        Returns:
            List of Dict in object_type schema.
        """
        intacct_object_type = INTACCT_OBJECTS[object_type]
        total_intacct_objects = []
        get_count = {
            'query': {
                'object': intacct_object_type,
                'select': {'field': 'RECORDNO'},
                'filter': {
                    'greaterthanorequalto': {
                        'field': GET_BY_DATE_FIELD,
                        'value': _format_date_for_intacct(from_date),
                    }
                },
                'pagesize': '1',
                'options': {'showprivate': 'true'},
            }
        }

        response = self.format_and_send_request(get_count)
        count = int(response['data']['@totalcount'])
        pagesize = 1000
        offset = 0
        for _i in range(0, count, pagesize):
            data = {
                'query': {
                    'object': intacct_object_type,
                    'select': {'field': fields},
                    'options': {'showprivate': 'true'},
                    'filter': {
                        'greaterthanorequalto': {
                            'field': GET_BY_DATE_FIELD,
                            'value': _format_date_for_intacct(from_date),
                        }
                    },
                    'pagesize': pagesize,
                    'offset': offset,
                }
            }
            intacct_objects = self.format_and_send_request(data)['data'][
                intacct_object_type
            ]
            # When only 1 object is found, Intacct returns a dict, otherwise it returns a list of dicts.
            if isinstance(intacct_objects, dict):
                intacct_objects = [intacct_objects]

            for record in intacct_objects:
                yield record

            offset = offset + pagesize

    def get_by_date_and_load_child_data(
        self, *, object_type: str, fields: List[str], from_date: dt.datetime
    ) -> List[Dict]:
        """
        Get multiple objects of a single type from Sage Intacct, filtered by GET_BY_DATE_FIELD (WHENMODIFIED) date.
        Also load the data using GET API instead of list. GET API will bring all the relations along with the basic objects.

        Returns:
            List of Dict in object_type schema.
        """
        intacct_object_type = INTACCT_OBJECTS[object_type]

        # First get the count of object that will be synchronized.
        get_count = {
            'query': {
                'object': intacct_object_type,
                'select': {'field': 'RECORDNO'},
                'filter': {
                    'greaterthanorequalto': {
                        'field': GET_BY_DATE_FIELD,
                        'value': _format_date_for_intacct(from_date),
                    }
                },
                'pagesize': '1',
                'options': {'showprivate': 'true'},
            }
        }

        response = self.format_and_send_request(get_count)
        count = int(response['data']['@totalcount'])
        pagesize = 1000
        offset = 0

        # Now that we have count of object, lets query the data in chunks
        for _i in range(0, count, pagesize):

            # First lets ket the RECORDNO for all object is current chunks.
            data = {
                'query': {
                    'object': intacct_object_type,
                    'select': {'field': 'RECORDNO'},
                    'options': {'showprivate': 'true'},
                    'filter': {
                        'greaterthanorequalto': {
                            'field': GET_BY_DATE_FIELD,
                            'value': _format_date_for_intacct(from_date),
                        }
                    },
                    'pagesize': pagesize,
                    'offset': offset,
                }
            }

            # Make the API call and convert each object to python Dict
            intacct_objects = self.format_and_send_request(data)['data'][
                intacct_object_type
            ]

            # When only 1 object is found, Intacct returns a dict, otherwise it returns a list of dicts.
            if isinstance(intacct_objects, dict):
                intacct_objects = [intacct_objects]

            # Create comma separated list of keys.
            keys = ""
            for record in intacct_objects:
                keys = keys + record['RECORDNO'] + ","
            keys = keys[:-1] if len(keys) > 0 else keys

            # Now let's get full object data in current chuck using read by key API.
            data = {
                'read': {
                    'object': intacct_object_type,
                    'keys': keys,
                    'fields': ','.join(fields)
                }
            }

            # Make the API call and convert each object to python Dict
            intacct_objects = self.format_and_send_request(data)['data'][
                intacct_object_type
            ]

            # Yield each object for processing.
            for record in intacct_objects:
                yield record

            # Set offset for next chunk.
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
        logger.info("fields_data")
        logger.info(response)
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
