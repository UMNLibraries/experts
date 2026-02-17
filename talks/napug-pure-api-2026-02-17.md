# NAPUG Pure API talk - 2026-02-17

For a breakout session at the 2026-02-17 North American Pure Users Group meeting

## Vocab
* Pure portal vs core/back end
* API
  * RESTful API
* Pure Web Services: old read-only API
* Pure API: new read-write API

## Both APIs
* Rich data model
  * Danish librarians take pride in and credit for it
* Unusually large number of collections/end points
* Lots of record types have many sub-records, especially Research Outputs

## Old Web Services vs. New API

### Web Services
* Read-only
* More filtering features
  * `(created|modified)(After|Before)` in POST requests
* changes collection
  * can include a datet string to get changes made after the given date
* No new features, 5.24 will be the last version

### API
* Allows reads _and_ writes
  * Many more security settings
* Few ways to filter results
* Not all WS collections are available
  * no changes collection
* Provides some collections/record types unavailable via WS
* Many new features in development, possibly including the two above
* Versioned?

## Pure API
* core admin
  * API keys
  * perms
* Swagger (OpenAPI) interactive docs
* RapiDoc: https://your.pure.domain/ws/api/rapidoc.html
* other docs

### Pure API writes
* unlike XML/Master List bulk imports, no referential integrity protections

## Pure Web Services
* core admin
  * API keys
  * perms
* Swagger interactive docs
* other docs

## Strangeness
* Merges are strange, from a RESTful perspective
  * Request for UUID of a record that did _not_ survive a merge will return the
    record that _did_ survive the merge, with a different UUID
  * The UUID of the now-defunct record will be in the `previousUuids` list of the
    surviving record
  * A RESTful API _should_ return a `301 - Moved Permanently` response in this case,
    but Pure's APIs just return the new record with a `200 - Success` response. 
  * True of both API and Web Services
* change collection
  * Thre change types: CREATE, UPDATE, DELETE
  * Only direct source of information about deleted records is change DELETEs,
    but we seem to get DELETEs for only ~40% of deleted records
  * No way to filter changes other than by date, and there are a _lot_ of changes

## UMN
* We support the entire University, not just a single school, college, or department
* Record counts
| Count   | Collection/record type |
|---------|------------------------|
| 386250  | Research Outputs       |
| 67804   | Persons                |
| 1323    | Organizational Units   |
| 722077  | External Persons       |
| 281543  | External Organizations |
|---------|------------------------|
