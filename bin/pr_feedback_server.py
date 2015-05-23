#! /usr/bin/env python

import tornado.web
import tornado.httpserver
import tornado.ioloop
import requests
import json
import os
import hashlib
import hmac
import argparse


#Since bamboo does not have api tokens you will need to provide a real user's password
#  If you don't want to store the password in plaintext in the config file you will
#  be prompted for it when the server starts up
password = None


def get_config(config_file):
    '''
    Loads and parses the json config file and returns
    a config object
    '''
    try:
        data = json.load(open(config_file))
        return data
    except ValueError:
        print "Config file {} has invalid json.".format(config_file)
    except OSError:
        print "Config file {} does not exist".format(config_file)
    return {}

def get_sha1_hmac(shared_secret, raw):
     '''
     Takes the shared secret and a raw string and generates
     and returns a sha1 hmac 
     '''
     hashed = hmac.new(str(shared_secret), str(raw), hashlib.sha1).hexdigest()
     return "sha1={}".format(hashed)

class GithubHandler(tornado.web.RequestHandler):
    '''
    Handle posts from github hook
    '''

    def verify_secret(self, request, config):
        '''
        Verify the shared secret, returns True on verified False otherwise
        '''
        ss = config.get("github_shared_secret")
        if not ss:
            print "No shared secret configured (github_shared_secret)"
            return
        gh_digest = request.headers.get("X-Hub-Signature")
        if not gh_digest:
            print "Did not recieve digest from github. Do you have it configured in the hook?"
            return
        local_digest = get_sha1_hmac(ss, request.body)
        if local_digest != gh_digest:
            print "Digest from github did not match our digest"
            print "GH   : {}".format(gh_digest)
            print "LOCAL: {}".format(local_digest)
            return
        else:
            return True

    def post(self):
        config_file = os.environ.get('BAMBOO_PR_FEEDBACK_CONFIG', "../config/config.json")
        config = get_config(config_file)

        if not self.verify_secret(self.request, config):
            return
        data = self.request.body
        try:
            data = json.loads(data)
        except ValueError:
            print "Recieved invalid json"
            print data
            return 
        plan = config.get("plan")
        host = config.get("bamboo_host")
        port = config.get("bamboo_port", 443)
        user = config.get("bamboo_user")
        password = config.get("bamboo_password", password)       

        bamboo_data = {}
        bamboo_data["pull_num"] = data.get("number")
        bamboo_data["pull_sha"] = data.get("head", {}).get("sha")

        run_bamboo_job(plan, host, port, user, password, bamboo_data) 

        self.finish()

def run_bamboo_job(plan, host, port, user, 
    password, bamboo_data):
    '''
    Post to bamboo server to kick off a job.
    '''
    
    params = ""
    for k,v in bamboo_data.iteritems():
        params += "&bamboo.variable.{}={}".format(k,v)          

    bamboo_queue_build = "https://{}:{}/builds/rest/api/latest/queue/{}?os_athType=basic{}"
    url = bamboo_queue_build.format(host, port, plan, params)
    headers = {}
    headers['Accept'] = 'application/json'     
    ret = requests.post(url, auth=(user,password), headers=headers)  
    pass

def parse_args():
    p = argparse.ArgumentParser(description = \
    '''
    Processes github hooks and activates bamboo builds via rest api
    ''')
    p.add_argument('--ssl-cert', help='location of ssl cert', required=True)
    p.add_argument('--ssl-key', help='location of ssl cert', required=True)
    return p.parse_args()

def main():
    args = parse_args()

    ssl_settings = {
        "certfile": args.ssl_cert,
        "keyfile": args.ssl_key
    }

    config_file = os.environ.get('BAMBOO_PR_FEEDBACK_CONFIG', "../config/config.json")
    config = get_config(config_file)
    application = tornado.web.Application([
        (r"/gh", GithubHandler)
    ])
    server = tornado.httpserver.HTTPServer(application, ssl_options=ssl_settings)
    server.listen(config.get("server_port", 80))

    global password
    if not config.get('bamboo_password'):
        password = raw_input('Please enter your bamboo password: \n').strip()

    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()

