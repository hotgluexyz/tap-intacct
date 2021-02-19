# tap-intacct

This is a [Singer](https://singer.io) tap that produces JSON-formatted data
following the [Singer
spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).

## Quick Start

1. Install

    ```bash
    pip install git+https://github.com/hotgluexyz/tap-intacct.git
    ```

2. Create the config file

   Create a JSON file called `config.json`. Its contents should look like:

   ```json
    {
        "start_date": "2010-01-01",
        "company_id": "<Intacct Company Id>",
        "sender_id": "<Intacct Sender Id>",
        "sender_password": "<Intacct Sender Password>",
        "user_id": "<Intacct User Id>",
        "user_password": "<Intacct User Password>"
    }
    ```

   The `start_date` specifies the date at which the tap will begin pulling data
   (for those resources that support this).

   The `company_id` is the Sage Intacct Company Id.

   The `sender_id` is the Sage Intacct Sender Id.

   The `sender_password` is the Sage Intacct Sender Password.

   The `user_id` is the Sage Intacct User Id.

   The `user_password` is the Sage Intacct User Password.

4. Run the Tap in Discovery Mode

    ```bash
    tap-intacct --config config.json --discover > catalog.json
    ```

   See the Singer docs on discovery mode
   [here](https://github.com/singer-io/getting-started/blob/master/docs/DISCOVERY_MODE.md#discovery-mode).

5. Run the Tap in Sync Mode

    ```bash
    tap-intacct --config config.json --catalog catalog.json
    ```
