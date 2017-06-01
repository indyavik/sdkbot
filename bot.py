from flask import Flask, jsonify , request, Response, render_template , session, abort, flash , url_for, redirect
from functools import wraps

import os, json,shutil
import requests, jinja2
import random
from bs4 import BeautifulSoup
from time import gmtime, strftime
from datetime import datetime
import hmac
import hashlib
from cron import helpers

app = Flask(__name__)

#key configurations 

swagger_url = 'https://raw.githubusercontent.com/Azure/azure-sdk-for-python/master/swagger_to_sdk_config.json' 
swagger_to_sdk = helpers.request_helper(swagger_url)
git_url = 'https://api.github.com/repos/Azure/azure-rest-api-specs/'
access_token = '2dd078a2a012e23bed1ff39015ead3675bc9f1d0'
this_repo = "https://api.github.com/repos/indyavik/azuresdk/issues"


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == 'azureuser' and password == 'secretsdk123'

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def check_secret(f):
    @wraps(f)
    def decorated (*args, **kwargs):
        secret = request.headers.get('X-Hub-Signature')
        mac = hmac.new('weare7', request.data , hashlib.sha1)
        print (str(mac.hexdigest()))

        if not str(mac.hexdigest()) == secret.split('=')[1] : 
            return jsonify({'Error' : 'secret not found'})

        return f(*args, **kwargs)

    return decorated


def request_helper(url, access_token=None):
    """
    helper function/method to call API using request and return JSON encoded object. 
    if fails or gets 404, raises error. 
    
    """
    if not access_token:
        access_token = '2dd078a2a012e23bed1ff39015ead3675bc9f1d0'
        
    r = requests.get(url, auth=('username', access_token))
    
    if r.status_code != 200:
        return 
    
    else:
        return r.json()


@app.route('/')
def names():
    data = {"Hello": ["You", "may", "get some", "donuts"]}
    return jsonify(data)


@app.route('/payload', methods=['GET', 'POST'])
@check_secret
def payload():

    event_name = request.headers.get('X-GitHub-Event')

    data = json.loads(request.data)

    action = data['action']

 
    if event_name == 'issues' and action == 'labeled' :
        #a label creation event. action = assign issue

        labels = data['label']['name'] 

        if 'KeyVault' in labels:
            issue_number = data['issue']['number']
            url = this_repo + "/" + str(issue_number)
            data = json.dumps({ 'assignees':['indyavik'] })
            r = requests.patch(url, data, auth=('username', access_token))

            if r.status_code == 200:

                return jsonify({'Action' : 'Successfully updated assignees for this issue'})


    if event_name == 'issue_comment' and data['action'] == 'created':

        comment = data['comment']['body']

        if comment.startswith('@bot'):

            atbot, action = set(comment.split(' ')[0:2])

            action_body = comment.split(' ')[2:]

            if action == 'generate' :

                pr_url = data['issue']['pull_request'].get('url') 
                repo = data['repository'].get('full_name')

                #get branch from github. 
                pr_json = request_helper(pr_url)
                branch = pr_json['head']['label'].split(':')[1] #e.g. 'bottest'
                generated_action = "docker run swagger-to-sdk {} -p {} -b {}".format(repo, action_body[0], branch)

                print generated_action

                return jsonify({'Ans' : generated_action})

            if action == 'list': 
                project = swagger_to_sdk['projects'][action_body[0]]
                azure_api_name, c_composite, c_swagger, sdk, namespace = helpers.parse_swagger_to_sdk_config(project)
                is_comp, folder_list, use_swagger =  helpers.get_key_folder_params_v3(git_url, azure_api_name)

                d = {}
                d['azure_api'] = azure_api_name
                
                if is_comp == 'No':
                    d['folders'] = folder_list
                    d['is_composite'] = 'no'

                    for i in folder_list:
                        url = git_url  + 'contents/' +  azure_api_name + '/' + i +'/swagger/'
                        swagger_content = request_helper(url)
                        if swagger_content and swagger_content[0].get('path'):
                            d[i] = swagger_content[0].get('path')

                    return jsonify(d) 

                else:
                    d['use_swagger'] = use_swagger
                    d['is_composite'] = 'yes'

                    return jsonify(d) 

            if action == 'update': 

                project = swagger_to_sdk['projects'][action_body[0]]
                azure_api_name, latest_folder, c_swagger, sdk, namespace = helpers.parse_swagger_to_sdk_config(project)
                is_comp, folder_list, use_swagger =  helpers.get_key_folder_params_v3(git_url, azure_api_name)

                d = {}
                d['azure_api'] = azure_api_name

                if is_comp == 'No' :

                    url = git_url  + 'contents/' +  azure_api_name + '/' + folder_list[-1] +'/swagger/'
                    swagger_content = request_helper(url)
                    d['swagger'] = swagger_content

                    return jsonify(d) 

                else:
                    d['is_composite'] = 'yes'
                    d['swagger']  = use_swagger

                    return jsonify(d) 


    return jsonify({'response' : 'recieved OK, no action taken'})

    #return 'Flask is running!'

if __name__ == '__main__':
    app.run()


