from hotglue_smoke_test.vcr.tap import VCRTapTestRunner


class ConnectorTapTestRunner(VCRTapTestRunner):
    # Config keys + xmltodict tag names (Intacct XML is lowercase, no underscores)
    TOKEN_KEYS = [
        *VCRTapTestRunner.TOKEN_KEYS,
        "company_id",
        "sender_id",
        "user_id",
        "companyid",
        "senderid",
        "userid",
        # Echoed in later request bodies; TOKEN_KEYS → same prefix*** in req+resp.
        "sessionid",
    ]

    # Control / pagination (client._post_request, get_by_date).
    # Date-time property names: singer Transformer rejects scrubbed values when format is
    # date/date-time (union of selected fields across migrated catalogs).
    # objectName / userDefinedDimension: get_dimension_values reads dimensions then queries.
    # Tap reads these from responses for auth, pagination, bookmarks, or compare keys.
    # Date-time fields that are only schema/Transformer concerns are left to the scrubber.
    PRESERVE_KEYS = {
        "status",
        "endpoint",
        "@totalcount",
        "objectName",
        "userDefinedDimension",
        # key_properties (scrubbed numeric PKs collide in compare)
        "RECORDNO",
        "VENDORID",
        "DEPARTMENTID",
        "ID",
        "id",
        "dimensionType",
        # replication keys (strptime / get_by_date)
        "WHENMODIFIED",
        "ENTRY_DATE",
        "ACCESSTIME",
        "updatedAt",
    }

    def module(self) -> str:
        return "tap_intacct"

    def launch(self):
        from tap_intacct import main

        main()


if __name__ == "__main__":
    ConnectorTapTestRunner.main()
