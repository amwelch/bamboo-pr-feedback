# bamboo-pr-feedback
Get the status of Bamboo builds in your Github pull requests

##Features

A simple web-server that fires a bamboo build plan on recipt of a github webhook post.

##Installation

	sudo pip install -r requirements.txt

##Configuration

First you will need to configure a webhook and add a shared secret
https://developer.github.com/v3/repos/hooks/

The url should point to the host:port that this server will listen on and the path /gh.
http://foo.com:8080/gh
Your git hook should be configured to fire only on pull request events.

###A note on Bamboo authentication
Right now Bamboo does not support an api key. The recomended setup is to add a special user for automation with only the necessary permissions.

This webserver does support an alternative setup. If a password is not configured in the config file it will prompt the user for a password on startup. This is mostly meant for testing and should not be used in a production environment.

config will be read from config/config.json by default. The path can be set with the environment variable BAMBOO_PR_FEEDBACK_CONFIG.

Example config.json:

	"server_port": PORT,
	"github_shared_secret": SECRET,
	"plan": BAMBOO_PLAN_NAME,  
	"bamboo_host": EXAMPLE.ATLASSIAN.NET,
	"bamboo_port": BAMBOO_PORT,
	"bamboo_user": USER,
	"bamboo_password": PASSWORD #optional (see note above)

###A not on Github authentication
To use run_lint.py you will need write permission to the status api and read permission on any repos you are operating on. Because of limitations in the OAuth scoping it can be necessary to use two seperate keys (one on an account with private repo read only access and one on an account with write but only the status api granted to the key). To support this there is an optional argument --gh-api-read that will be used to read comments on the repo. If the argument isn't used then the same key will be used for everything.

##Usage

	pr_feedback_server.py --ssl-cert PATH_TO_SSL_CERT --ssl-key PATH_TO_SSL_KEY
        # Run lint and update github comment status for the lint context
        run_lint.py --pr-num NUM --repo-base  https://api.github.com/repos/OWNER/REPO --path PATH_TO_LOCAL_REPO --gh-api-write API_KEY  --sha COMMIT_SHA

##Testing

	#test-client.py will mimic a github webhook post
	./test-client.py --pr-num SOME_PULL_REQUEST --commit-sha SOME_COMMIT_HASH --url https://localhost:10010/gh --secret SOME_SECRET

##Author

Alexander welch <amwelch3 (at) gmail.com>

##License

MIT
