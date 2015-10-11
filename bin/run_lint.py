#! /usr/bin/env python

import requests
import fnmatch
import subprocess
import argparse


def post_result(base, failed_files, api_key, sha):
    url = base + '/statuses/{sha}?access_token={api_key}'.format(sha=sha,
                                                                 api_key=api_key)
    if any(failed_files):
        status = 'failure'
        description = 'Lint failed for: ' + " ".join(failed_files)
        # Sad Panda
        link = 'http://fc08.deviantart.net/fs70/f/2010/149/a/7/Sad_Panda_Chibi_by_mongrelssister.png'
    else:
        status = 'success'
        description = 'Lint passed'
        link = 'http://i.imgur.com/DPVM1.png'
    data = {"state": status, "target_url": link,
            "description": description, "context": "lint"}
    headers = {}
    headers['Accept'] = 'application/json'
    requests.post(url, data=json.dumps(data), headers=headers)


def run_lint(path, files, lint='pyflakes', pattern='*.py'):
    failed = []
    for fname in files:
        if not fnmatch.fnmatch(fname, pattern):
            continue
        try:
            subprocess.check_call([lint + " " + fname], shell=True, cwd=path)
        except subprocess.CalledProcessError:
            failed.append(fname)
    return failed


def get_changed_files(api_key, repo_base, pr_num):
    '''
    Retrieve the list of changed files for a pull request
    '''
    "https://api.github.com/repos/deepfield/pipedream/statuses/$bamboo_pull_sha?access_token={api_key}"
    url = repo_base + "/pulls/{num}/files?access_token={api_key}".format(num=pr_num, api_key=api_key)
    req = requests.get(url)
    data = req.json()
    files = [v['filename'] for v in data]
    return files


def parse_args():
    p = argparse.ArgumentParser(description ='''
    Get changed files from a pull-request and check for lint errors
    ''')
    p.add_argument('--pr-num', help='pull-request num', required=True)
    p.add_argument('--repo-base', help='repo-base-url', required=True)
    p.add_argument('--path', help='path to repo', required=True)
    p.add_argument('--gh-api', help='gh api key', required=True)
    p.add_argument('--sha', help='commit hash', required=True)
    return p.parse_args()


def main():
    args = parse_args()
    files = get_changed_files(args.gh_api, args.repo_base, args.pr_num)
    failed = run_lint(args.path, files)
    post_result(args.repo_base, failed, args.gh_api, args.sha)

if __name__ == '__main__':
    main()
