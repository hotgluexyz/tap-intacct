REQUIRED_CONFIG_KEYS = [
    'company_id',
    'sender_id',
    'sender_password',
    'user_id',
    'user_password',
]

KEY_PROPERTIES = {
    'accounts_payable_bills': ["RECORDNO"],
    'accounts_payable_bill_items': ["RECORDNO"],
    'accounts_payable_payments': ["RECORDNO"],
    'accounts_payable_payment_details': ["RECORDNO"],
    'accounts_payable_vendors': ["VENDORID"],
    "accounts_payable_bank_accounts": ["RECORDNO"],
    "checking_accounts": ["RECORDNO"],
    "savings_accounts": ["RECORDNO"],
    "card_accounts": ["RECORDNO"],
    "classes": ["RECORDNO"],
    "tasks": ["RECORDNO"],
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
    'departments': ["DEPARTMENTID"],
    'audit_history': ["ID"],
    'locations': ["RECORDNO"],
    'budget_details': ["RECORDNO"],
    'budget_list': ["RECORDNO"],
    'po_documents': ["RECORDNO"],
    'employees': ["RECORDNO"],
}

# List of available objects with their internal object-reference/endpoint name.
INTACCT_OBJECTS = {
    "accounts_payable_bills": "APBILL",
    "accounts_payable_bill_items": "APBILLITEM",
    "accounts_payable_payments": "APPYMT",
    "accounts_payable_payment_details": "APPYMTDETAIL",
    "accounts_payable_vendors": "VENDOR",
    "accounts_payable_bank_accounts": "PROVIDERBANKACCOUNT",
    "checking_accounts": "CHECKINGACCOUNT",
    "savings_accounts": "SAVINGSACCOUNT",
    "card_accounts": "CREDITCARD",
    "classes": "CLASS",
    "tasks": "TASK",
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
    "departments": "DEPARTMENT",
    "audit_history": "AUDITHISTORY",
    "locations": "LOCATION",
    "budget_list": "GLBUDGETHEADER",
    "budget_details": "GLBUDGETITEM",
    "po_documents": "PODOCUMENT",
    "employees": "EMPLOYEE",
}

REP_KEYS = {
    "audit_history" : "ACCESSTIME",
    "budget_details": None
}

IGNORE_FIELDS =["PASSWORD"]



GET_BY_DATE_FIELD = "WHENMODIFIED"

DEFAULT_API_URL = 'https://api.intacct.com/ia/xml/xmlgw.phtml'
