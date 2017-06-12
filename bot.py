from flask import Flask, jsonify , request, Response, render_template , session, abort, flash , url_for, redirect
from functools import wraps

import os, json,shutil
import requests, jinja2
import hmac
import hashlib

import utils
import asyncio


app = Flask(__name__)

#key configurations 

swagger_url = 'https://raw.githubusercontent.com/Azure/azure-sdk-for-python/master/swagger_to_sdk_config.json' 

git_url = 'https://api.github.com/repos/Azure/azure-rest-api-specs/'

github_access_token = os.environ.get('TOKEN')


this_repo = "https://api.github.com/repos/indyavik/azuresdk/issues"

issue_assignees = { 'KeyVault' : ['indyavik'] }

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

    if event_name == 'issue_comment' : 

        issue_url = payload['issue']['url']
        repo_url = payload['issue']['repository_url']

        if payload.get('comment'):

            comment = payload['comment']['body']
            print ('comment is :' + comment)

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
                            utils.at_generate(payload))

                print (response)

                if response:

                    pr = loop.run_until_complete(utils.post_response(issue_url + '/comments', {'body': response } ))
                    if 'success' in pr:
                        return (response)
                    else:
                        return (pr)


            #@bot list dns 
            if comment_action == 'list': 


                project = swagger_to_sdk['projects'][action_body[0]]
                azure_api_name, c_composite, c_swagger, sdk, namespace = utils.parse_swagger_to_sdk_config(project)
                print ("azure_api: " + azure_api_name)

                print(loop.run_until_complete(
                                                utils.get_azure_folder_params(git_url, azure_api_name) ))#)

                is_comp, folder_list, use_swagger =  loop.run_until_complete(
                                                utils.get_azure_folder_params(git_url, azure_api_name) )#git_url, azure_folder_name, gituser, gittoken )
                

            
                if is_comp == 'No':

                    d = {}
                    d['azure_api'] = azure_api_name
                    d['is_composite'] = 'no'

                    string_response = ''

                    for i in range(len(folder_list)):
                        d[str(i)] = folder_list[i]
                        string_response += str(i) +':' + folder_list[i] +','

                    pr = loop.run_until_complete(utils.post_response(issue_url + '/comments' , {'body': string_response } ))

                    if 'success' in pr:
                        return jsonify(d)
                    else:
                        return jsonify(pr)
      

                else:
                    d = {}
                    d['azure_api'] = azure_api_name
                    d['use_swagger'] = use_swagger
                    d['is_composite'] = 'yes'

                    string_response = 'Composite project. No folders to list'

                    pr = loop.run_until_complete(utils.post_response(issue_url + '/comments', {'body': string_response } ))

                    if 'success' in pr:
                        return jsonify(d)
                    else:
                        return jsonify(pr)

            #@bot update dns 2 

            if comment_action == 'update': 
                print('ere')

                if not action_body[1]: #1..2...3...

                    response = 'Error : unspecified folder number (1..2...3..)'

                    pr = loop.run_until_complete(utils.post_response(issue_url + '/comments', {'body' : response } ))

                    if 'success' in pr:
                        return (response)
                    else:
                        return (pr)

     
                swagger_to_sdk_project_name = action_body[0] #billing, cdn etc. 

                project = swagger_to_sdk['projects'][swagger_to_sdk_project_name]


                azure_api_name, c_composite, c_swagger, sdk, namespace = utils.parse_swagger_to_sdk_config(project)
                
                is_comp, folder_list, use_swagger =  loop.run_until_complete(
                                                utils.get_azure_folder_params(git_url, azure_api_name) )


                if is_comp == 'No':
                    #get the swagger path 
                    if (int(action_body[1]) < len(folder_list)):
                        folder = folder_list[int(action_body[1])]
                    else:
                        response = 'Error : list value' +  action_body[1] + 'exceed the length'
                        pr = loop.run_until_complete(utils.post_response(issue_url + '/comments', {'body' : response } ))

                        return jsonify({'Error' : 'list value exceed the length'})

                    #get updated swagger for this folder, e.g.  arm-billing/2017-04-24-preview/swagger/billing.json
                   
                    updated_swagger = loop.run_until_complete(
                                    utils.get_swagger_path_from_folders(git_url, azure_api_name, folder= folder))

                    #update the project and return

                    project['swagger'] = updated_swagger

                    updated_project_json = {}

                    updated_project_json[swagger_to_sdk_project_name]  = project

                    response =  "``` JSON \n" + json.dumps(updated_project_json) + " \n ```" 

                    pr = loop.run_until_complete(utils.post_response(issue_url + '/comments', {'body' : response } ))
                    #r = requests.post(issue_url + '/comments', json.dumps(response),  auth=('username', github_access_token))

                    if 'success' in pr:
                        return (response)
                    else:
                        return(pr)



    #label => KeyVault

    if event_name == 'issues' and action == 'labeled' :

        print('checking keyvalue')

        issue_url = payload['issue']['url']
        print(issue_url)
        repo_url = payload['issue']['repository_url']

        label = payload['label']['name'] 
        assignees = issue_assignees.get(label)

        if assignees:

            response = loop.run_until_complete(
                        utils.at_label(issue_url, assignees))

            print (response)

            if response:
                pr = loop.run_until_complete(utils.post_response(issue_url + '/comments', {'body' : response } ))

                if 'success' in pr:
                    return (response)
                else:
                    return (pr)
     
        
    return jsonify({'response' : 'recieved OK, no action taken'})



if __name__ == '__main__':
    app.run()
