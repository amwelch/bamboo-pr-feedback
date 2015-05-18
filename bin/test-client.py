#! /usr/bin/env python

import requests
import json
import os
import hashlib
import hmac

import pr_feedback_server

def main():
    config_file = os.environ.get('BAMBOO_PR_FEEDBACK_CONFIG', "../config/config.json")
    config = pr-feedback-server.get_config(config_file)

    bamboo_data = {}
    bamboo_data['pull_num'] = '3'
    bamboo_data['pull_sha'] = 'foo'
    bamboo_data['author'] = 'bar'
   

    pr_feedback_server.run_bamboo_job(config['plan'], config['host'], config['port'],
        config['user'], config['password'], bamboo_data)

if __name__ == '__main__':
    main()

