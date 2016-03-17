#! /usr/bin/env python

import requests
import fnmatch
import subprocess
import argparse
import json


def get_header_string(prefix='JS'):
    ''' The string that we use to identify comments written by the linter '''
    buf = '''AUTOMATIC {} LINT RESULTS DO NOT EDIT\n'''.format(prefix)
    return buf


def get_lint_comment(base, api_key, pr_num):
    '''
    Retrieves all comments on an issue from github and searches for a
    comment starting with the string returned by get_header_string()
    '''
    template = '/issues/{num}/comments?access_token={api_key}'
    url = base + template.format(num=pr_num, api_key=api_key)
    headers = {}
    headers['Accept'] = 'application/json'
    comment_id = None
    req = requests.get(url, headers=headers)
    for comment in req.json():
        if comment['body'].startswith(get_header_string()):
            comment_id = comment['id']
    return comment_id


def create_or_update_lint_comment(base, api_key, pr_num, errors):
    '''
    If we haven't already made a comment on a pull request then make
    a new one. Otherwise update that comment with the current error set.
    '''
    body = get_header_string() + '\n' + generate_buf(errors)
    comment_id = get_lint_comment(base, api_key, pr_num)
    data = {'body': body}
    if comment_id:
        template = '/issues/comments/{comment_id}?access_token={api_key}'
        url = base + template.format(num=pr_num,
                                     comment_id=comment_id, api_key=api_key)
        requests.patch(url, headers=get_headers(), data=json.dumps(data))
    else:
        template = '/issues/{num}/comments?access_token={api_key}'
        url = base + template.format(num=pr_num, api_key=api_key)
        requests.post(url, headers=get_headers(), data=json.dumps(data))


def get_headers():
    '''
    General set of headers used in requests to github
    '''
    return {'Accept': 'application/json'}


def post_result(base, failed_files, api_key, sha, prefix='JS'):
    '''
    Update the status for teh lint context per commit SHA
    '''
    template = '/statuses/{sha}?access_token={api_key}'
    url = base + template.format(sha=sha, api_key=api_key)
    if any(failed_files):
        status = 'failure'
        description = '{} Lint failed'.format(prefix)
        # Sad Panda
        link = 'http://fc08.deviantart.net/fs70/f/2010/149/a/7/Sad_Panda_Chibi_by_mongrelssister.png'
    else:
        status = 'success'
        description = '{} Lint passed'.format(prefix)
        # Just ship it
        link = 'http://i.imgur.com/DPVM1.png'
    data = {"state": status, "target_url": link,
            "description": description, "context": "{} lint".format(prefix)}
    headers = {}
    headers['Accept'] = 'application/json'
    requests.post(url, data=json.dumps(data), headers=headers)


def generate_buf(errors):
    '''
    Generate the body of the comment given a set of errors
    '''
    if errors:
        msg = []
        for fname, errors in errors.iteritems():
            msg += ['JS Lint Errors for {}'.format(fname)]
            for error in errors:
                line, col, errstr = error
                msg.append('\n\t{},\t{}:\t{}'.format(line, col, errstr))
        msg = '\n'.join(msg)
    else:
        msg = 'Lint all good :shipit:'
    return msg


def post_errors(errors, base, api_key, sha):
    '''
    One comment per file per commit with the violations.
    '''
    template = '/commits/{sha}/comments?access_token={api_key}'
    url = base + template.format(sha=sha, api_key=api_key)
    for fname, errors in errors.iteritems():
        msg = generate_buf(errors)
        data = {'body': msg,
                'path': fname,
                'position': 1,
                'line': None}
        headers = {}
        headers['Accept'] = 'application/json'
        requests.post(url, data=json.dumps(data), headers=headers)


def get_errors(lint_output):
    '''
    Given the lint output extract a dict of {fname: [errors]}
    '''
    errors = {}
    total = "errors"
    for line in lint_output:
        if line:
            try:
                fname, errstr = line.split(':')
                ecol, erow, errmsg = errstr.split(',')
                errors.setdefault(fname, [])
                errors[fname].append((ecol, erow, errmsg))
            except:
                total = fname
    return errors, total

def does_match(fname, patterns):
    ret = False
    for pattern in patterns:
        if fnmatch.fnmatch(fname, pattern):
            ret = True
            break
    return ret

# Javascript inline html and template files are not supported.  Another
# Good reason to ensure there is no js in html.
def run_lint(path, files, lint='jshint', patterns=['*.js']):
    '''
    Given a lint and file pattern run the lint over all files in the
    change set that match that pattern.
    '''
    failed = []
    output = []
    for fname in files:
        if does_match(fname, patterns) is False:
            continue
        try:
            subprocess.check_output([lint + " " + fname], shell=True, cwd=path)
        except subprocess.CalledProcessError as e:
            output += e.output.split('\n')
            failed.append(fname)
    return failed, output


def get_changed_files(api_key, repo_base, pr_num):
    '''
    Retrieve the list of changed files for a pull request
    '''
    template = "/pulls/{num}/files?access_token={api_key}"
    url = repo_base + template.format(num=pr_num, api_key=api_key)
    req = requests.get(url)
    data = req.json()
    files = [v['filename'] for v in data]
    return files


def parse_args():
    p = argparse.ArgumentParser(description='''
    Get changed files from a pull-request and check for lint errors
    ''')
    p.add_argument('--pr-num', help='pull-request num', required=True)
    p.add_argument('--repo-base', help='repo-base-url', required=True)
    p.add_argument('--path', help='path to repo', required=True)
    p.add_argument('--gh-api-write',
                   help='gh api key used to post comments/status',
                   required=False)
    p.add_argument('--gh-api-read',
                   help='gh api key used to read changed files ' +
                        '(defaults to write if not specified)')
    p.add_argument('--sha', help='commit hash', required=True)
    return p.parse_args()


def main():
    args = parse_args()
    write_key = args.gh_api_write
    if args.gh_api_read:
        read_key = args.gh_api_read
    else:
        read_key = args.gh_api_write
    files = get_changed_files(read_key, args.repo_base, args.pr_num)
    failed, errors = run_lint(args.path, files)
    errors, total = get_errors(errors)
    create_or_update_lint_comment(args.repo_base, read_key,
                                  args.pr_num, errors)
    post_result(args.repo_base, failed, write_key, args.sha)

if __name__ == '__main__':
    main()
