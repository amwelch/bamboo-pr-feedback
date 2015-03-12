#! /usr/bin/env python

import tornado.web
import tornado.ioloop
import requests
import json
import hashlib
import hmac

def get_config(config_file="../config/config.json"):
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
     hashed = hmac.new(shared_secret, raw, hashlib.sha1)
     return hashed.digest().encode("base64").rstrip("\n")

class GithubHandler(tornado.web.RequestHandler):
    '''
    Handle posts from github hook
    '''
    bamboo_queue_build = "https://{}:{}/bamboo/rest/api/latest/queue/{}?os_athType=basic{}"
    def verify_secret(self, request):
        '''
        Verify the shared secret, returns True on verified False otherwise
        '''
        config = get_config()
        ss = config.get("github_shared_secret")
        if not ss:
            print "No shared secret configured (github_shared_secret)"
            return
        gh_digest = request.headers.get("X-Hub-Signature")
        if not gh_digest:
            print "Did not recieve digest from github. Do you have it configured in the hook?"
            return
        local_digest = get_sha1_hmac(request.body)
        if local_digest != gh_digest:
            print "Digest from github did not match our digest"
            print "GH   : {}".format(gh_digest)
            print "LOCAL: {}".format(local_digest)
            return
        else:
            return True

    def post(self):

        data = self.request.body
        try:
            data = json.loads(data)
        except ValueError:
            print "Recieved invalid json"
            print data
 
        config = get_config()
        plan = config.get("plan")
        host = config.get("bamboo_host")
        port = config.get("bamboo_port", 443)
        user = config.get("bamboo_user")
        password = config.get("bamboo_password")       

        bamboo_data = {}
        bamboo_data["pull_num"] = data.get("pull_num")
        bamboo_data["pull_sha"] = data.get("pull_sha")
        bamboo_data["author"] = data.get("author")
 
        params = ""
        for k,v in bamboo_data.iteritems():
            params += "?bamboo.variable.{}={}".format(k,v)          

        url = bamboo_queue_build.format(host, port, plan, params)
        headers = {}
        headers['Accept'] = 'application/json'     
        requests.post(url, auth=(user,password), headers=headers)  

        self.finish()

class BambooHandler(tornado.web.RequestHandler):
    def post(self):
        print "placeholder"
        self.write("placeholder")
        self.finish()

def main():
    config = get_config()
    application = tornado.web.Application([
        (r"/gh", GithubHandler),
        (r"/bh", BambooHandler)
    ])
    application.listen(config.get("server_port", 80))
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()

