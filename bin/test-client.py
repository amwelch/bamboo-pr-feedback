#! /usr/bin/env python

import requests
import json
import argparse
import os
import hashlib
import hmac

import pr_feedback_server

#Copied from gh
BODY_TEMPLATE ={
  "action": "opened",
  "number": "",
  "pull_request": {
    "url": "foo",
    "id": 14251,
    "number": "",
    "state": "open",
    "locked": False,
    "title": "test pr",
    "body": "test webhook pr",
    "created_at": "2015-05-21T01:36:07Z",
    "updated_at": "2015-05-21T01:36:07Z",
    "head": {
       "sha": ""
    }
  },
}


def parse_args():
    p = argparse.ArgumentParser(description = \
    '''
    Mimics a git hook
    ''')
    p.add_argument('--commit-sha', help='hash of the commit', required=True)
    p.add_argument('--pr-num', help='pull-request num', required=True)
    p.add_argument('--url', help='host to post to', required=True)
    p.add_argument('--secret', help='Shared secret to use', required=True)
    return p.parse_args()

def main():
    args = parse_args()

    body = BODY_TEMPLATE
    body['number'] = args.pr_num
    body['pull_request']["number"] = args.pr_num
    body['pull_request']["head"]["sha"] = args.commit_sha

    headers = {}
    headers['X-Hub-Signature'] = pr_feedback_server.get_sha1_hmac(args.secret, json.dumps(body))

    requests.post(args.url, data=json.dumps(body), headers=headers)

if __name__ == '__main__':
    main()

