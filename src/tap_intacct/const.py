REQUIRED_CONFIG_KEYS = [
    'company_id',
    'sender_id',
    'sender_password',
    'user_id',
    'user_password',
]

KEY_PROPERTIES = {
    'accounts_payable_bills': ["RECORDNO"],
    'accounts_payable_vendors': ["RECORDNO"],
    'general_ledger_accounts': ['RECORDNO'],
    'general_ledger_details': ["RECORDNO"],
    'general_ledger_journal_entries': ["RECORDNO"],
    'projects': ["RECORDNO"],
}

# List of available objects with their internal object-reference/endpoint name.
INTACCT_OBJECTS = {
    "accounts_payable_bills": "APBILL",
    "accounts_payable_vendors": "VENDOR",
    "general_ledger_accounts": "GLACCOUNT",
    "general_ledger_details": "GLDETAIL",
    "general_ledger_journal_entries": "GLBATCH",
    "projects": "PROJECT",
}

GET_BY_DATE_FIELD = "WHENMODIFIED"

DEFAULT_API_URL = 'https://api.intacct.com/ia/xml/xmlgw.phtml'
