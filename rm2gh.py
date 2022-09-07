from redminelib import Redmine
import github3
import github3.utils as ghutils
import json
import sys
import time
import urllib.request


try:
    from config import *
except ImportError:
    print('Failed to read configuration from config.py')
    sys.exit(1)


def create_issue(rm_issue):
    body = '***Issue migrated from Redmine: ' \
           '{}/issues/{}***\n' \
           '*Originally created by {} at {} UTC.*\n\n{}'.format(
            REDMINE_URL, rm_issue.id, rm_issue.author,
            rm_issue.created_on, rm_issue.description)

    comments = []
    note = 1
    for journal in rm_issue.journals:
        comment = '***Comment migrated from Redmine: ' \
                  '{}/issues/{}#note-{}***\n' \
                  '*Originally created by {} at {} UTC.*\n\n{}'.format(
                    REDMINE_URL, rm_issue.id, note, journal.user,
                    journal.created_on, journal.notes)
        comments.append({'body': comment,
                         'created_at':
                             ghutils.timestamp_parameter(journal.created_on)})
        note = note + 1

    gh_issue = {
        'title': rm_issue.subject,
        'body': body,
        'created_at': rm_issue.created_on,
        'assignee': None,
        'milestone': None,
        'labels': None,
        'assignee': None,
        'comments': comments
    }

    return gh_issue


def get_imported_issue_id(url):
    hdr = {'Authorization': 'token {}'.format(GITHUB_TOKEN),
           'Accept': 'application/vnd.github.golden-comet-preview+json'}

    req = urllib.request.Request(url, headers=hdr)
    data = urllib.request.urlopen(req).read()

    issue = json.loads(data)

    if issue['status'] == 'imported':
        return int(issue['issue_url'].split('/')[-1])
    else:
        return 0


def main():
    # Login to Redmine and get the project
    redmine = Redmine(REDMINE_URL,
                      version='4.0.7',
                      key=REDMINE_TOKEN)
    project = redmine.project.get(REDMINE_PROJECT)

    # Login to Github
    github = github3.login(token=GITHUB_TOKEN)
    repository = github.repository(GITHUB_USER, GITHUB_REPO)

    # Iterate through the issues on Redmine
    issue_count = 0
    for rm_issue in project.issues:
        if issue_count == MAX_ISSUES:
            break

        # Create the Github issue data
        gh_issue = create_issue(rm_issue)

        # Perform the import
        imp_issue = repository.import_issue(**gh_issue)

        # Get the public ID of the new comment
        new_issue_id = get_imported_issue_id(imp_issue.url)
        while new_issue_id == 0:
            time.sleep(1)
            new_issue_id = get_imported_issue_id(imp_issue.url)

        new_issue = github.issue(GITHUB_USER, GITHUB_REPO, new_issue_id)

        print('Migrated {}/issues/{} to {}'.format(
            REDMINE_URL, rm_issue.id, new_issue.html_url))

        issue_count = issue_count + 1

    print('Migrated {} issues.'.format(issue_count))


if __name__ == "__main__":
    main()
