from flask import Flask, jsonify , request, Response, render_template , session, abort, flash , url_for, redirect
from functools import wraps

import os, json,shutil
import requests, jinja2
import hmac
import hashlib
from cron import helpers
import utils
import asyncio

app = Flask(__name__)

#key configurations 

swagger_url = 'https://raw.githubusercontent.com/Azure/azure-sdk-for-python/master/swagger_to_sdk_config.json' 

git_url = 'https://api.github.com/repos/Azure/azure-rest-api-specs/'
github_user = 'indyavik'
github_access_token = '767d1a76e004ec56d5d57c7394974a9e6b7a6a0e'
this_repo = "https://api.github.com/repos/indyavik/azuresdk/issues"
issue_assignees =['indyavik']

swagger_to_sdk = utils.request_helper(swagger_url, github_access_token)

def check_secret(f):
    @wraps(f)
    def decorated (*args, **kwargs):
        secret = request.headers.get('X-Hub-Signature')
        mac = hmac.new(b'weare7', request.data , hashlib.sha1)
        print (str(mac.hexdigest()))

        if not str(mac.hexdigest()) == secret.split('=')[1] : 
            return jsonify({'Error' : 'secret not found'})

        return f(*args, **kwargs)

    return decorated



@app.route('/')
def names():
    data = {"Hello": ["You", "may", "get some", "donuts"]}
    return jsonify(data)


@app.route('/payload', methods=['GET', 'POST'])
@check_secret
def payload():

    loop = asyncio.get_event_loop()
    
    payload = json.loads(request.data)
    event_name = request.headers.get('X-GitHub-Event')
    action = payload['action']

    comment = None 

    if payload.get('comment'):

        comment = payload['comment']['body']
        print (comment)

    if comment and comment.startswith('@bot'):
        
        atbot, comment_action = tuple(comment.split(' ')[0:2])

        action_body = comment.split(' ')[2:]

        print('action_body')
        print(action_body)

        print('comment-action is' + comment_action)

        #@bot generate dns 
        if (action == 'created' 
            and comment_action == 'generate') :

            response = loop.run_until_complete(
                        utils.at_generate(payload, github_user, github_access_token))

            print (response)
            if response:
                return jsonify(response)


        #@bot list dns 
        if comment_action == 'list': 

            project = swagger_to_sdk['projects'][action_body[0]]
            azure_api_name, c_composite, c_swagger, sdk, namespace = utils.parse_swagger_to_sdk_config(project)
            
            is_comp, folder_list, use_swagger =  loop.run_until_complete(
                                            utils.get_azure_folder_params(git_url, azure_api_name, github_user, github_access_token) )#git_url, azure_folder_name, gituser, gittoken )
            
            if is_comp == 'No':

                response = loop.run_until_complete(
                    utils.get_swagger_from_folders(git_url, azure_api_name, folder_list, github_user, github_access_token ))

                if response:
                    return jsonify(response)
  

            else:
                d = {}
                d['azure_api'] = azure_api_name
                d['use_swagger'] = use_swagger
                d['is_composite'] = 'yes'

                return jsonify(d) 

        #@bot update dns 2 

    #label => KeyVault

    if event_name == 'issues' and action == 'labeled' :
        print('checking keyvalue')

        labels = payload['label']['name'] 

        if 'KeyVault' in labels:

            response = loop.run_until_complete(
                        utils.at_label(payload, github_user, github_access_token, this_repo, issue_assignees))

            print (response)
            if response:
                return jsonify(response)


        return jsonify({'response' : 'recieved OK, no action taken'})


    #return 'Flask is running!'

if __name__ == '__main__':
    app.run()


