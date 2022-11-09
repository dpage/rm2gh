import os
import json
import sys
import tempfile
import time
import urllib.request

import boto3
import github3
import github3.utils as ghutils
from redminelib import Redmine

try:
    from config import *
except ImportError:
    print('Failed to read configuration from config.py')
    sys.exit(1)


def main():
    # Login to Redmine and get the project
    redmine = Redmine(REDMINE_URL,
                      version=REDMINE_VERSION,
                      key=REDMINE_TOKEN)
    project = redmine.project.get(REDMINE_PROJECT)

    # Iterate through the issues on Redmine
    if ISSUE_STATUS != 'open' and ISSUE_STATUS != 'closed':
        issue_status = '*'
    else:
        issue_status = ISSUE_STATUS

    issues = redmine.issue.filter(sort='id', status_id=issue_status,
                                  project_id=REDMINE_PROJECT,
                                  include=['journals'])
    num_issues = 0
    for rm_issue in issues:
        num_issues = num_issues + 1

        print('rewrite ^/projects/pgadmin4/issues/new https://github.com/postgres/pgadmin4/issues/new permanent;'.format(rm_issue.id))


if __name__ == "__main__":
    main()