REQUIRED_CONFIG_KEYS = [
    'company_id',
    'sender_id',
    'sender_password',
    'user_id',
    'user_password',
]

KEY_PROPERTIES = {
    'accounts_payable_bills': ["RECORDNO"],
    'accounts_payable_payments': ["RECORDNO"],
    'accounts_payable_vendors': ["VENDORID"],
    'accounts_payable_payments': ["RECORDNO"],
    'accounts_payable_payment_requests': ["RECORDNO"],
    'accounts_payable_payment_details': ["RECORDNO"],
    'general_ledger_accounts': ['RECORDNO'],
    'general_ledger_details': ["RECORDNO"],
    'general_ledger_journal_entries': ["RECORDNO"],
    'general_ledger_journal_entry_lines': ["RECORDNO"],
    'projects': ["RECORDNO"],
    'invoices': ["RECORDNO"],
    'adjustments': ["RECORDNO"],
    'customers': ["RECORDNO"],
    'deposits': ["RECORDNO"],
    'items': ["RECORDNO"],
    'invoice_items': ["RECORDNO"],
    'adjustment_items': ["RECORDNO"],
    # 'tax_records': ["RECORDNO"], # not working
    'tax_details': ["RECORDNO"],
    'departments': ["DEPARTMENTID"],
}

# List of available objects with their internal object-reference/endpoint name.
INTACCT_OBJECTS = {
    "accounts_payable_bills": "APBILL",
    "accounts_payable_payments": "APPYMT",
    "accounts_payable_vendors": "VENDOR",
    "accounts_payable_payments": "APPYMT",
    "accounts_payable_payment_requests": "APPAYMENTREQUEST",
    "accounts_payable_payment_details": "APPYMTDETAIL",
    "general_ledger_accounts": "GLACCOUNT",
    "general_ledger_details": "GLDETAIL",
    "general_ledger_journal_entries": "GLBATCH",
    "general_ledger_journal_entry_lines": "GLENTRY",
    "projects": "PROJECT",
    "invoices": "ARINVOICE",
    "adjustments": "ARADJUSTMENT",
    "customers": "CUSTOMER",
    "deposits": "DEPOSIT",
    "items": "ITEM",
    "invoice_items": "ARINVOICEITEM",
    "adjustment_items": "ARADJUSTMENTITEM",
    # "tax_records": "TAXRECORD", # not working
    "tax_details": "TAXDETAIL",
    "departments": "DEPARTMENT",
}

IGNORE_FIELDS =["PASSWORD"]

NO_DATE_FILTER = [ 
    "tax_details"
]

GET_BY_DATE_FIELD = "WHENMODIFIED"

DEFAULT_API_URL = 'https://api.intacct.com/ia/xml/xmlgw.phtml'
