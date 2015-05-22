#! /usr/bin/env python

import requests
import json
import argparse
import os
import hashlib
import hmac

import pr_feedback_server

#Copied from gh
BODY_TEMPLATE = """
{
  "action": "opened",
  "number": "{number}",
  "pull_request": {
    "url": "foo",
    "id": 14251,
    "number": {number},
    "state": "open",
    "locked": false,
    "title": "test pr",
    "body": "test webhook pr\r\n",
    "created_at": "2015-05-21T01:36:07Z",
    "updated_at": "2015-05-21T01:36:07Z",
    "closed_at": null,
    "merged_at": null,
    "head": {
      "sha": "{sha}",
    }
  }
}
"""

def parse_args():
    p = argparse.ArgumentParser(description = \
    '''
    Connect to a chatserver and send some messages
    ''')
    p.add_argument('--commit-sha', help='hash of the commit', required=True)
    p.add_argument('--pr-num', help='pull-request num', required=True)
    p.add_argument('--url', help='host to post to', required=True)
    return p.parse_args()

def main():
    args = parse_args()

    body = body.format(number=args.pr_num,sha=args.commit_sha)

    headers = {}
    headers['X-Hub-Signature'] = pr_feedback_server.get_sha1_hmac(args.secret, body)

    requests.post(args.url, data=body, headers=headers)

if __name__ == '__main__':
    main()

