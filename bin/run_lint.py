#! /usr/bin/env python

import requests
import re
import shutil
import os
import fnmatch
import subprocess
import argparse
import json


def get_header_string(language):
    ''' The string that we use to identify comments written by the linter '''
    buf = '''AUTOMATIC {} LINT RESULTS DO NOT EDIT\n'''.format(language.upper())
    return buf


def get_lint_comment(base, api_key, pr_num, language):
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
        if comment['body'].startswith(get_header_string(language)):
            comment_id = comment['id']
    return comment_id


def create_or_update_lint_comment(base, api_key, pr_num, errors, language):
    '''
    If we haven't already made a comment on a pull request then make
    a new one. Otherwise update that comment with the current error set.
    '''
    body = get_header_string(language) + '\n' + generate_buf(errors)
    comment_id = get_lint_comment(base, api_key, pr_num, language)
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

def upload_lint(api_key, output):
    url = 'https://api.github.com/gists?access_token={}'.format(api_key)
    data = {'description': 'Lint Results',
            'public': False,
            'files': {'Results.txt': {'content': output}}}
    
    response = requests.post(url, data=json.dumps(data))
    return response.json()['html_url']
    

def post_result(base, failed_files, api_key, sha, language, result_url):
    '''
    Update the status for teh lint context per commit SHA
    '''
    template = '/statuses/{sha}?access_token={api_key}'
    url = base + template.format(sha=sha, api_key=api_key)
    if any(failed_files):
        status = 'failure'
        description = '{} lint failed'.format(language)
    else:
        status = 'success'
        description = '{} lint passed'.format(language)
    data = {"state": status, "target_url": result_url,
            "description": description, "context": "{} lint".format(language)}
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
            msg += ['__Lint Errors for {}__'.format(fname)]
            for error in errors:
                line, col, errstr = error
                msg.append('\n\t{},{}:\t{}'.format(line, col, errstr))
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


def get_errors(lint_output, regex, files):
    "^(?P<file>[^:]+):(?P<line>[0-9]+) (?P<errstr>.*)$"
    '''
    Given the lint output extract a dict of {fname: [errors]}

    Some common regexs:
        pyflakes: "^(?P<file>[^:]+):(?P<line>[0-9]+) (?P<errstr>[.*]+)$"
        jshint: '^(?P<file>[^:]+): line (?P<line>[0-9]+), col (?P<col>[0-9]+), (?P<errstr>.+)$'
    '''
    errors = {}
    total = "errors"
    for line in lint_output:
        if line:
            m = re.search(regex, line)
            if m:
                 data = {'file': '',
                         'line': '',
                         'errstr': '',
                         'col': '0'}
                 for k in data:
                     try:
                         data[k] = m.group(k)
                     except IndexError:
                         pass
             
                 errors.setdefault(data['file'], [])
                 errors[data['file']].append((data['line'], data['col'], data['errstr']))
            else:
                 total = line
    return errors, total

def does_match(fname, patterns):
    ret = False
    for pattern in patterns:
        if fnmatch.fnmatch(fname, pattern):
            ret = True
            break
    return ret

def run_lint(files, lint, patterns, data_directory='/tmp/lint'):
    '''
    Given a lint and file pattern run the lint over all files in the
    change set that match that pattern.
    '''
    failed = []
    before_output = []
    output = []
    all_output = []
    lint_files = [f for f in files.keys() if does_match(f, patterns)]
    for fname in lint_files:

        path = os.path.join(data_directory, fname)
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        with open(path, 'w') as fp:
            fp.write(files[fname]['before'])

        try:
            subprocess.check_output([lint + " " + path], shell=True)
        except subprocess.CalledProcessError as e:
            before_output += set(e.output.split('\n'))

        with open(path, 'w') as fp:
            fp.write(files[fname]['after'])
        try:
            subprocess.check_output([lint + " " + path], shell=True)
        except subprocess.CalledProcessError as e:
            all_output.append(lint + ' ' + fname)
            all_output.append(e.output)
            lines = e.output.split('\n')
            lines in [l for l in lines if l not in before_output]
            if lines:
                output += lines
                failed.append(fname)

        shutil.rmtree(data_directory)

    return failed, output, '\n'.join(all_output)


def get_changed_files(api_key, read_api_key, repo_base, pr_num):
    '''
    Retrieve the list of changed files for a pull request
    '''
    template = "/pulls/{num}/files?access_token={api_key}"
    url = repo_base + template.format(num=pr_num, api_key=api_key)
    req = requests.get(url)
    data = req.json()

    template = "/pulls/{num}?access_token={api_key}"
    url = repo_base + template.format(num=pr_num, api_key=api_key)
    base_sha = requests.get(url).json()['base']['sha']

    files = {}
    for v in data:
        content_url = v['contents_url'] + '&access_token={api_key}'.format(api_key=api_key)
        content = requests.get(content_url).json()['content'].decode('base64')
        base_content_url = content_url.split('?')[0] + '?ref={sha}&access_token={api_key}'.format(sha=base_sha, api_key=api_key)
        base_content = requests.get(base_content_url).json()['content'].decode('base64')
        files[v['filename']] = {'after': content, 'before': base_content}
    return files

def parse_args():
    p = argparse.ArgumentParser(description='''
    Get changed files from a pull-request and check for lint errors
    ''')
    p.add_argument('--pr-num', help='pull-request num', required=True)
    p.add_argument('--repo-base', help='repo-base-url', required=True)
    p.add_argument('--language', help='Language for the lint', required=True)
    p.add_argument('--lint', help='Lint to run', required=True)
    p.add_argument('--upload', help='Upload lint results to gist', action='store_true')
    p.add_argument('--regex', help='Optional regex to parse lint output. '\
                   + ' Supported named capture groups:\n\tfile, line, errstr, col')
    p.add_argument('--patterns', help='Glob patterns to run on', required=True, nargs='+')
    p.add_argument('--gh-api-write',
                   help='gh api key used to post comments/status',
                   required=True)
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
    files = get_changed_files(read_key, args.gh_api_write, args.repo_base, args.pr_num)
    failed, errors, buf = run_lint(files, args.lint, args.patterns)
    if args.upload:
        result_url = upload_lint(write_key, buf)
    else:
        result_url = ''

    # Some default regexs
    if not args.regex:
        default_regexs = {'pyflakes': '^(?P<file>[^:]+):(?P<line>[0-9]+): (?P<errstr>.+)$',
                          'jshint': '^(?P<file>[^:]+): line (?P<line>[0-9]+), col (?P<col>[0-9]+), (?P<errstr>.+)$'}
        regex = default_regexs.get(args.lint) or '$^'
    else:
        regex = args.regex
    errors, total = get_errors(errors, regex, files)
    create_or_update_lint_comment(args.repo_base, read_key,
                                  args.pr_num, errors, args.language)
    post_result(args.repo_base, failed, write_key, args.sha, args.language,
                result_url)

if __name__ == '__main__':
    main()
