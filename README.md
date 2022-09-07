# rh2gh - Redmine to Github Issue Migrator

This is a WIP tool for migrating issues from Redmine to Github.

It will iterate through the issues on a Redmine project, and migrate them to
issues on a Github project, adding notes and links to indicate what data was
migrated, including the timing and author where that cannot be set on Github
(the author in particular is very hard, as it would require pre-mapping Redmine
usernames to Github usernames).

## Usage

1) copy _config.py.in_ to _config.py_ and edit as required.
2) Create a virtualenv, and install the requirements from _requirements.txt_.
3) With the virtualenv activated, run:
    ```bash
    python3 rm2gh.py
    ```
4) Wait a very long time.

Note that Github have a 5000 request per day API limit. Each issue that's 
migrated may require multiple API requests. Plan your migration accordingly.

## TODO

* Add the tracker name as a tag
* Add attachment support:
  * Upload the attachments to an S3 bucket (there's no Github upload API)
  * Create a Github comment for each attachment, inlining images and with
    a link to other content
  * Intermix attachments with comments, based on date ordering.
* Check Textile vs. Markdown formatting works as expected.
* Add support for batching (e.g. select source issues by range).
* Add a link to the migrated issue on Redmine, to the new Github issue.