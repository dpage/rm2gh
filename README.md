# rh2gh - Redmine to Github Issue Migrator

**NOTE:** this was built for the sole purpose of migrating the pgAdmin 4 Redmine
project at https://redmine.postgresql.org/projects/dave-test to Github. It's 
entirely possible^Wprobable that there is some project-specific code in here!

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

* Add support for batching (e.g. select source issues by range).
* Decode header changes on Redmine to a readable string.