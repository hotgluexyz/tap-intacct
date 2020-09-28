# tap-intacct-api

This is a [Singer](https://singer.io) tap that produces JSON-formatted data
following the [Singer
spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).
<!---
This tap:

- Pulls raw data from [Mailgun](https://documentation.mailgun.com/en/latest/api_reference.html)
- Extracts the following resources:
  - [Bounces](https://documentation.mailgun.com/en/latest/api-suppressions.html#bounces)
  - [Complaints](https://documentation.mailgun.com/en/latest/api-suppressions.html#view-all-complaints)
  - [Domains](https://documentation.mailgun.com/en/latest/api-domains.html)
  - [Events](https://documentation.mailgun.com/en/latest/api-events.html#events)
  - [Messages](https://documentation.mailgun.com/en/latest/api-events.html#viewing-stored-messages)
  - [Unsubscribes](https://documentation.mailgun.com/en/latest/api-suppressions.html#unsubscribes)
- Outputs the schema for each resource
- Incrementally pulls data based on the input state


## Notes
### Event availability
The Mailgun API has limited data available from the Events endpoint.

Each account will have a different retention period, based on your subscription. You can find your retention period in [your dashboard](https://app.mailgun.com/app/dashboard).

### Messages
[Stored messages](https://documentation.mailgun.com/en/latest/api-sending.html#retrieving-stored-messages) can only be synced via IDs retrieved from the Events endpoint.

Stored messages are [retained in the system for 3 days](https://documentation.mailgun.com/en/latest/api-sending.html#deleting-stored-messages) and automatically purged after this retention period, so at most you will only be able to retrieve Message data from 3 days prior to the initial sync.

### Suppressions (Bounces, Unsubscribes and Complaints)
During the initial run of this tap, Suppressions will be synced in full. Subsequent syncs (with a state file) will sync each suppression as they are encountered in the events logs.

The reason for this is that [Mailgun only provides responses of all suppressions, or a single suppression.](https://documentation.mailgun.com/en/latest/api-suppressions.html)

To avoid running full syncs on the above streams on each run, ensure you use a state file after the initial sync. Alternatively, `"full_suppression_sync": false` can be added to `config.json` to override the full sync on the initial (and subsequent) runs.

### Base URL
The Base URL used by this tap is `https://api.mailgun.net/v3`, if your domain was created in Mailguns EU region, you will need to use `https://api.eu.mailgun.net/v3`.

The default Base URL can be overridden in the config file, e.g. `"base_url": "https://api.eu.mailgun.net/v3"`


### Configuration settings
Running the the tap requires a config.json file. Example with the minimal settings:
```
{
    "private_key": "key-************************",
    "start_date": "2020-06-01T00:00:00Z"
}
```
Full list of options in config.json:

| Property | Type | Required | Description | Default |
|---|---|---|---|---|
| private_key | String | Y | Authentication is required when using the Mailgun API, you can find your private key inside your Mailgun Control Panel  | N/A |
| start_date | String | Y | Used on first sync to indicate how far back to grab records. Start dates should conform to the RFC3339 specification. | N/A |
| base_url | String | N | All API calls start with a base URL. Mailgun allows the ability to send and receive email in either US region or EU region. Be sure to use the appropriate base URL based on which region you’ve created your domain in. | https://api.mailgun.net/v3/ |
| full_suppression_sync | Boolean | N | If true, suppressions (bounces, unsubscribes and complaints) will be synced in full regardless of start_date. | False is state file, True if not |
| event_lookback | Integer | N | Amount of hours to subtract from the state timestamp, to catch any late-arriving events. | 1 |

---

Copyright &copy; 2018 Stitch
--->
