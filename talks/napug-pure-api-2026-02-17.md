# NAPUG Pure API talk - 2026-02-17

For a breakout session at the 2026-02-17 North American Pure Users Group meeting

## Vocab
* Pure portal vs core/back end
* [API: Application Programming Interface](https://en.wikipedia.org/wiki/API)
* RESTful API: [REST (REpresentational State Transfer)](https://en.wikipedia.org/wiki/REST)
* [JSON: JavaScript Object Notation](https://en.wikipedia.org/wiki/JSON)
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
  * `createdAfter`, `createdBefore`, `modifiedAfter`, `modifiedBefore` in POST requests
* `changes` collection
  * Requests can include a date string to get changes made after a given date
* No new features, 5.24 will be the last version

#### Documentation
* Interactive
  * Swagger: https://experts.umn.edu/ws/api/524/api-docs/#/
* Other
  * PureWeb Service - persistent version (5.24 and later): https://experts.umn.edu/ws/api/524/api-docs/documentation/Content/Topics/Web_Services_Intro.htm

#### Settings
In Pure Core/Back end, under __Administrator > Security__:
* Permissions: __Ws__
* API Keys: __Api keys__

### API
* Allows reads _and_ writes
  * Unlike XML/Master List bulk imports, no referential integrity protections, other differences
  * [Pure API vs XML Synchronisation](https://helpcenter.pure.elsevier.com/pure-api-vs-xml-synchronisation)
  * Many more security settings
* Few ways to filter results
* Not all Web Services collections are available
  * no `changes` collection
* Provides some collections/record types unavailable via Web Services
* Many new features in development, possibly including the two above
* Versioned?

#### Documentation
* Interactive
  * RapiDoc: https://experts.umn.edu/ws/api/rapidoc.html
  * Swagger/OpenAPI: https://experts.umn.edu/ws/api/api-docs/index.html?url=/ws/api/openapi.yaml#/
* Other
  * [Pure API user guide](https://helpcenter.pure.elsevier.com/pure-api-home)

#### Settings
In Pure Core/Back end, under __Administrator > Pure API__:
* Permissions: __Access definitions__
* API Keys: __User API Access__

## Strangeness
* Merges are strange, from a RESTful perspective
  * Request for UUID of a record that did _not_ survive a merge will return the
    record that _did_ survive the merge, with a different UUID
  * The UUID of the now-defunct record will be in the `previousUuids` list of the
    surviving record
  * A RESTful API _should_ return a `301 - Moved Permanently` response in this case,
    but Pure's APIs just return the new record with a `200 - Success` response. 
  * True of both API and Web Services
* `changes` collection
  * Three change `type`s: `CREATE`, `UPDATE`, `DELETE`
  * Only direct source of information about deleted records is `changes` `DELETE`s,
    but we seem to get `DELETE`s for only ~40% of deleted records
  * No way to filter `changes` other than by date, and there are a _lot_ of changes
* Pure stores data in Cassandra, _not_ an Relational Database Management System (RDBMS)
  * Cassandra is a [NoSQL, wide-column store database](https://cassandra.apache.org/doc/latest/cassandra/developing/data-modeling/data-modeling_rdbms.html).
  * Attempting to transform Pure data into a [traditional relational schema](https://en.wikipedia.org/wiki/Relational_database)
    (tables with rows and columns) will likely be extremely difficult, at best.

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

* Due to those high record counts, we try to incrementally update our local database
  with only created and modified records since our last update. Given the strangeness
  described above, it may be better to just download all records every time instead,
  if your record counts make that practical.
* ELT > ETL
  * ETL (Extract, Transform, and Load) is the more traditional approach
  * Given the volume, complexity, and strangeness of the Pure data,
    as described above, we load raw JSON Pure records into Oracle, and
    transform only the small fraction of data we need for reports, using
    the [Oracle JSON API](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/adjsn/json-in-oracle-database.html).
  * Example reports: https://github.com/UMNLibraries/experts_dw/tree/main/reports
