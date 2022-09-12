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


def s3_upload(s3, attachment, path):
    directory = tempfile.mkdtemp()

    attachment.download(savepath=directory, filename=attachment.filename)

    # Figure out a content type
    try:
        extra_args = {'ContentType': attachment.content_type,
                      'ACL': "public-read"}
    except:
        extra_args = {'ACL': "public-read"}

    s3.upload_file(os.path.join(directory, attachment.filename),
                   S3_BUCKET_NAME, path,
                   ExtraArgs=extra_args)

    os.remove(os.path.join(directory, attachment.filename))
    os.rmdir(directory)


def format_changelog(changes, rm_issue, redmine):
    if len(changes) == 0:
        return ''

    log = '**Redmine ticket header update:**\n\n' \
          'Name | Old Value | New Value\n' \
          '-----|-----------|----------'

    for change in changes:
        if change['property'] == 'attachment':
            name = 'Attachment added'
            old_value = ''
            new_value = change['new_value'] or ''

        elif change['property'] == 'attr':
            old_value = change['old_value']
            new_value = change['new_value']

            if change['name'] == 'assigned_to_id':
                if old_value is not None:
                    old_value = str(redmine.user.get(int(old_value)))
                if new_value is not None:
                    new_value = str(redmine.user.get(int(new_value)))

            elif change['name'] == 'fixed_version_id':
                if old_value is not None:
                    try:
                        old_value = str(redmine.version.get(int(old_value)))
                    except:
                        old_value = 'Unknown'
                if new_value is not None:
                    try:
                        new_value = str(redmine.version.get(int(new_value)))
                    except:
                        new_value = 'Unknown'

            elif change['name'] == 'priority_id':
                if old_value is not None:
                    old_value = \
                        str(redmine.enumeration.filter(
                            resource='issue_priorities').get(int(old_value)))
                if new_value is not None:
                    new_value = \
                        str(redmine.enumeration.filter(
                            resource='issue_priorities').get(int(new_value)))

            elif change['name'] == 'status_id':
                if old_value is not None:
                    old_value = str(redmine.issue_status.get(int(old_value)))
                if new_value is not None:
                    new_value = str(redmine.issue_status.get(int(new_value)))

            elif change['name'] == 'tracker_id':
                if old_value is not None:
                    old_value = str(redmine.tracker.get(int(old_value)))
                if new_value is not None:
                    new_value = str(redmine.tracker.get(int(new_value)))

            else:
                pass

            name = '{} changed'.format(
                change['name'].replace('_', ' ').title().replace(' Id', ' '))
            old_value = old_value or ''
            new_value = new_value or ''

        elif change['property'] == 'cf':
            try:
                name = '{} changed'.format(
                    rm_issue.custom_fields.filter(
                        id=int(change['name']))[0].name)
            except:
                name = 'Unknown custom field changed'
            old_value = change['old_value'] or ''
            new_value = change['new_value'] or ''

        elif change['property'] == 'relation':
            name = 'Relationship ({}) changed'.format(change['name'])
            if change['old_value'] is not None:
                old_value = 'RM #{}'.format(change['old_value'])
            else:
                old_value = ''
            if change['new_value'] is not None:
                new_value = 'RM #{}'.format(change['new_value'])
            else:
                new_value = ''

        else:
            name = '{} ({}) changed'.format(
                change['property'], change['name'])
            old_value = change['old_value'] or ''
            new_value = change['new_value'] or ''

        log = '{}\n{} | {} | {}'.format(log, name, old_value, new_value)

    return log


def format_attachment(attachment, issue_id, s3):
    # Construct the new comment and append it to the list
    filename = attachment.filename.replace(' ', '_')

    # Figure out a content type
    try:
        content_type = attachment.content_type
    except:
        content_type = ''

    if content_type.startswith('image/'):
        comment = '***Image migrated from Redmine: ' \
                  '{}/attachments/download/{}***\n' \
                  '*Originally created by **{}** at {} UTC.*\n\n' \
                  '![{}]({}/{}/{}-{})\n\n**Filename:** {}'.format(
                    REDMINE_URL, attachment.id, attachment.author,
                    attachment.created_on, filename,
                    S3_BUCKET_URL, issue_id, attachment.id,
                    filename, filename)
    else:
        comment = '***Attachment migrated from Redmine: ' \
                  '{}/attachments/download/{}***\n' \
                  '*Originally created by **{}** at {} UTC.*\n\n' \
                  '{}/{}/{}-{}'.format(
                    REDMINE_URL, attachment.id, attachment.author,
                    attachment.created_on, S3_BUCKET_URL, issue_id,
                    attachment.id, filename)

    if attachment.description != '':
        comment = '{}\n\n**Description:** {}'\
            .format(comment, attachment.description)

    if not DEBUG:
        s3_upload(s3,
                  attachment,
                  'redmine/{}/{}-{}'.format(
                      issue_id, attachment.id, filename))

    return comment


def format_journal(journal, rm_issue, note, project):
    # Attempt to get notes. These may be empty, or non-existent if the
    # only change was to the Redmine ticket header.
    notes = ''
    try:
        notes = journal.notes
    except:
        pass

    # Construct the new comment and append it to the list
    comment = '***Comment migrated from Redmine: ' \
              '{}/issues/{}#note-{}***\n' \
              '*Originally created by **{}** at {} UTC.*'.format(
                REDMINE_URL, rm_issue.id, note, journal.user,
                journal.created_on)

    # Add any notes
    if notes != '':
        comment = '{}\n\n{}'.format(comment, notes)

    # Add any metadata changes
    comment = '{}\n\n{}' \
        .format(comment, format_changelog(journal.details, rm_issue, project))

    return comment


def get_comment_list(rm_issue, redmine, s3):
    sources = []
    journal_id = 0
    for journal in rm_issue.journals:
        sources.append({'id': journal_id,
                        'ts': journal.created_on,
                        'type': 'j'})
        journal_id = journal_id + 1

    attachment_id = 0
    for attachment in rm_issue.attachments:
        sources.append({'id': attachment_id,
                        'ts': attachment.created_on,
                        'type': 'a'})
        attachment_id = attachment_id + 1

    sources = sorted(sources, key=lambda d: d['ts'])

    comments = []
    note = 1
    for source in sources:
        if source['type'] == 'j':
            journal = rm_issue.journals[source['id']]
            comment = format_journal(journal, rm_issue, note, redmine)
            comments.append({'body': comment,
                             'created_at':
                            ghutils.timestamp_parameter(journal.created_on)})

        elif source['type'] == 'a':
            attachment = rm_issue.attachments[source['id']]
            comment = format_attachment(attachment, rm_issue.id, s3)
            comments.append({'body': comment,
                             'created_at':
                            ghutils.timestamp_parameter(
                                attachment.created_on)})

        note = note + 1

    return comments


def create_issue(rm_issue, redmine, repository, s3):
    # Construct the new ticket body/description
    try:
        author = rm_issue.author
    except:
        author = 'Unknown'

    body = '***Issue migrated from Redmine: ' \
           '{}/issues/{}***\n' \
           '*Originally created by **{}** at {} UTC.*\n\n{}'.format(
            REDMINE_URL, rm_issue.id, author,
            rm_issue.created_on, rm_issue.description)

    comments = get_comment_list(rm_issue, redmine, s3)

    labels = [rm_issue.tracker.name.title()]

    # Add custom labels
    for field in REDMINE_CUSTOM_FIELDS:
        try:
            label = rm_issue.custom_fields.filter(name=field)[0].value
            if label != '':
                labels.append(label)
        except:
            pass

    # Add the corresponding milestone, if there is a fixed version
    milestone_id = None
    milestone_name = None
    try:
        milestone_name = rm_issue.fixed_version.name
    except:
        pass

    if milestone_name is not None:
        for milestone in repository.milestones(state='all'):
            if milestone.title == milestone_name:
                milestone_id = milestone.number

    # Create the Github import data
    gh_issue = {
        'title': '{} (RM #{})'.format(rm_issue.subject, rm_issue.id),
        'body': body,
        'created_at': rm_issue.created_on,
        'assignee': None,
        'milestone': milestone_id,
        'labels': labels,
        'assignee': None,
        'comments': comments
    }

    return gh_issue


def get_imported_issue_id(url):
    # Call the import URL. When the import is complete, the public URL
    # will be included in the issue_url field.
    hdr = {'Authorization': 'token {}'.format(GITHUB_TOKEN),
           'Accept': 'application/vnd.github.golden-comet-preview+json'}

    req = urllib.request.Request(url, headers=hdr)
    data = urllib.request.urlopen(req).read()

    issue = json.loads(data)

    if issue['status'] == 'failed':
        print('Issue import failed: {}'.format(issue))
        sys.exit(1)

    if issue['status'] == 'imported':
        return int(issue['issue_url'].split('/')[-1])
    else:
        return 0


def clear_github_labels(repository):
    # Clear labels
    labels = repository.labels()
    for label in labels:
        label.delete()


def migrate_versions(project, repository):
    for milestone in repository.milestones(state='all'):
        if not milestone.delete():
            print('Failed to delete milestone "{}"'.format(milestone))

    versions = project.versions

    for version in versions:
        due_date = None
        try:
            due_date = '{}T00:00:00Z'.format(version.due_date)
        except:
            pass

        try:
            repository.create_milestone(version.name,
                                        state=version.status,
                                        description=version.description,
                                        due_on=due_date)

            print('Migrated version "{}" (state: {}, due date: {})'.format(
                version.name, version.status, due_date))
        except Exception as e:
            print('Failed to migrate version "{}": {}'
                  .format(version.name, e))


def redmine_linkback(redmine, rm_issue, url):
    note = 'h1. WARNING: Issue Migrated to Github\n\n' \
           'This issue has been migrated to Github: {}\n\n' \
           'Please ensure any further updates are made on Github.'.format(url)

    redmine.issue.update(rm_issue.id, notes=note)


def migrate_issues(previous, redmine, github, repository, s3):
    # Iterate through the issues on Redmine
    if ISSUE_STATUS != 'open' and ISSUE_STATUS != 'closed':
        issue_status = '*'
    else:
        issue_status = ISSUE_STATUS

    issues = redmine.issue.filter(sort='id', status_id=issue_status,
                                  project_id=REDMINE_PROJECT,
                                  include=['journals',
                                           'attachments',
                                           'versions'])[:MAX_ISSUES]
    num_issues = 0
    num_migrated = 0
    num_skipped = 0
    for rm_issue in issues:
        num_issues = num_issues + 1

        # Skip previously migrated RMs, if enabled
        if TRACK_STATUS and (rm_issue.id in previous):
            num_skipped = num_skipped + 1
            continue

        # Create the Github issue data
        gh_issue = create_issue(rm_issue, redmine, repository, s3)

        if not DEBUG:
            # We're going to loop over the import attempt here, as sometimes
            # the Github import API seems to get "stuck" reporting 'pending'
            # as the state. When this happens, it never seems to end up
            # importing, so we'll just give up and retry.
            new_issue = None

            while new_issue is None:
                # Perform the import
                imp_issue = repository.import_issue(**gh_issue)

                # Get the public ID of the new comment
                new_issue_id = get_imported_issue_id(imp_issue.url)
                sleep_time = 0
                while new_issue_id == 0 and sleep_time < 20:
                    time.sleep(sleep_time)
                    sleep_time = sleep_time + 2
                    new_issue_id = get_imported_issue_id(imp_issue.url)

                if new_issue_id != 0:
                    new_issue = github.issue(GITHUB_OWNER,
                                             GITHUB_REPO,
                                             new_issue_id)

            # Close the issue, if necessary
            is_closed = False
            try:
                if rm_issue.closed_on is not None:
                    is_closed = True
            except:
                pass

            if is_closed:
                new_issue.create_comment('Issue closed on Redmine.')
                new_issue.close()

            if REDMINE_LINKBACK:
                redmine_linkback(redmine, rm_issue, new_issue.html_url)

            print('Migrated {}/issues/{} to {}'.format(
                REDMINE_URL, rm_issue.id, new_issue.html_url))

        else:
            print(gh_issue)

        if TRACK_STATUS:
            with open('migrated_ids.txt', 'a') as f:
                f.write('{}\n'.format(rm_issue.id))

        num_migrated = num_migrated + 1

    print('Migrated {} issues out of {}. {} previously migrated'.format(
        num_migrated, num_issues, num_skipped))


def main():
    # Login to Redmine and get the project
    redmine = Redmine(REDMINE_URL,
                      version=REDMINE_VERSION,
                      key=REDMINE_TOKEN)
    project = redmine.project.get(REDMINE_PROJECT)

    # Login to Github
    github = github3.login(token=GITHUB_TOKEN)
    repository = github.repository(GITHUB_OWNER, GITHUB_REPO)

    # Login to S3
    session = boto3.Session(profile_name=AWS_CLI_PROFILE)
    s3 = session.client('s3')

    previous = []
    if TRACK_STATUS:
        with open('migrated_ids.txt') as file:
            lines = file.readlines()
            previous = [int(line.rstrip()) for line in lines]

    if CLEAR_LABELS and not DEBUG:
        if len(previous) > 0:
            print('Not clearing labels as {} issues have already been '
                  'migrated.'.format(len(previous)))
        else:
            clear_github_labels(repository)

    if CLEAR_MILESTONES and not DEBUG:
        if len(previous) > 0:
            print('Not clearing and migrating milestones as {} issues have '
                  'already been migrated.'.format(len(previous)))
        else:
            migrate_versions(project, repository)

    migrate_issues(previous, redmine, github, repository, s3)


if __name__ == "__main__":
    main()
