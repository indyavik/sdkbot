import requests, json
import asyncio
import http
import io
import json
import re
import os
from functools import wraps

import aiohttp
import gidgethub
import gidgethub.aiohttp


from aiohttp import web

def request_helper(url, access_token):
    """
    helper function/method to call API using request and return JSON encoded object. 
    if fails or gets 404, raises error. 
    
    """
        
    r = requests.get(url, auth=('username', access_token))
    
    if r.status_code != 200:
        return 
    
    else:
        return r.json()

def parse_swagger_to_sdk_config(project):
#count the #  of slashes 1 ->, composite file. , 3 =>swagger file with datefolder. > 3 staggered/subprojects. 
#Use the fact that folder -=2015, 2016, 2017. ..starts with 20

    sdk = project['output_dir'].split('/')[0]

    namespace = project['autorest_options']['Namespace']

    if not namespace:
        namespace = ''

    swagger_file_path = project['swagger']

    if not swagger_file_path:
        return None 

    if 'swagger' in swagger_file_path:
        #not a composite
        split_path = swagger_file_path.split('/swagger/')   
        azure_api = '/'.join(split_path[0].split('/')[0:-1])
        folder, swagger_name = split_path[0].split('/')[-1], split_path[-1]


    else:
        #is a composite file. 
        folder = 'Composite'
        split_path = swagger_file_path.split('/')
        azure_api, swagger_name = split_path[0], split_path[-1]

    #print azure_api, folder, swagger_name


    #print azure_api_spec_folder, date_folder, swagger_file
    return (azure_api, folder, swagger_name, sdk, namespace)


async def get_azure_folder_params(git_url, azure_folder_name):
    
    async with aiohttp.ClientSession() as session:

        gh = gidgethub.aiohttp.GitHubAPI(session, 'username' ,oauth_token=os.environ.get('TOKEN'))
        try:
            rcomposite = await gh.getitem(git_url + 'contents/' + azure_folder_name)

            if not rcomposite:
                return None 
            #print(rcomposite)
            most_recent_composite_status = 'No' 
            swagger = None
            folders =[]

            for r in rcomposite:
                path = r['path']
                folder = path.split(azure_folder_name +'/')[1]

                if folder.startswith('20') or folder.startswith('/20'): 
                    folders.append(folder)

                if '.json' in path:
                    most_recent_composite_status = 'Yes'
                    swagger=path

            if not swagger and folders:
                target_url = git_url + 'contents/' + azure_folder_name + '/' + folders[-1] + '/swagger/'

                r_file = await gh.getitem(target_url)
                swagger =''
                for r in r_file:
                    #print r
                    if '.json' in r.get('name'):
                        swagger = r.get('path')


        except gidgethub.BadRequest as exc:
            print(exc.status_code)
            return "Error" + exc.status_code
        
        
        return (most_recent_composite_status, sorted(folders), swagger)


async def get_swagger_path_from_folders(git_url, azure_folder_name, folder_list=None, folder=None):

    """
    returns a swagger path for a specific folder. 
    if a list of folders are proived --> returns a dictionary with keys = folder, and value = swagger path 

    """

    if (not folder and folder_list):
        return {'error' : 'incorrect inputs'}

    if folder_list:

        d = {}
        d['azure_api'] = azure_folder_name
        d['folders'] = folder_list
        d['is_composite'] = 'no'

        async with aiohttp.ClientSession() as session:
            gh = gidgethub.aiohttp.GitHubAPI(session, 'username' ,oauth_token=os.environ.get('TOKEN'))
            for f in folder_list:
                url = git_url  + 'contents/' +  azure_folder_name + '/' + f +'/swagger/'
                swagger_content = await gh.getitem(url)
                if (swagger_content and swagger_content[0].get('path') ):
                    d[f] = swagger_content[0].get('path')
                else:
                    d[f] = 'swagger not found'

        return d 

    if folder:
        #returns a swagger path for a given folder. 
        async with aiohttp.ClientSession() as session:

            gh = gidgethub.aiohttp.GitHubAPI(session, 'username' ,oauth_token=os.environ.get('TOKEN'))
            url = git_url  + 'contents/' +  azure_folder_name + '/' + folder +'/swagger/'
            swagger_content = await gh.getitem(url)

            if (swagger_content and swagger_content[0].get('path') ):
                return swagger_content[0].get('path')

async def post_response(post_repo_url, response):
    """Post a response by github bot to the issue where the @bot request originated """

    async with aiohttp.ClientSession() as session:

        gh = gidgethub.aiohttp.GitHubAPI(session, 'username' ,oauth_token=os.environ.get('TOKEN'))

        try:
            await gh.post(post_repo_url, data= response )
            return "success"

        except gidgethub.BadRequest as exc:
            print(exc.status_code)
            return "Error" + exc.status_code

async def at_generate(event_data_dict):
    """Response to comments such as '@bot generate dns' """
    
    pr_url = event_data_dict['issue']['pull_request'].get('url') 
    repo = event_data_dict['repository'].get('full_name')
    comment = event_data_dict['comment']['body']
    action_body = comment.split(' ')[2:]
    repo2 =  action_body[0]
  
    #get branch name via github api 
    async with aiohttp.ClientSession() as session:

        #gh = gidgethub.aiohttp.GitHubAPI(session, 'indyavik',oauth_token=".....")

        gh = gidgethub.aiohttp.GitHubAPI(session, 'username' ,oauth_token=os.environ.get('TOKEN'))

        try:
            data = await gh.getitem(pr_url)
            branch = data['head']['label'].split(':')[1] #e.g. 'bottest'
            
        except gidgethub.BadRequest as exc:
            print(exc.status_code)
            return "Error" + exc.status_code
            
    if branch:
        generated_action = "docker run swagger-to-sdk {} -p {} -b {}".format(repo, repo2, branch)
        return generated_action



async def at_label(post_repo_url, assignee_list):
    """Response to label creation 'KeyVault' - > assign issue to a 'list' of users. """

    async with aiohttp.ClientSession() as session:

        gh = gidgethub.aiohttp.GitHubAPI(session, 'username' ,oauth_token=os.environ.get('TOKEN'))

        try:
            
            await gh.post(post_repo_url, data= { 'assignees':assignee_list} )

            return 'Successfully assigned the issue to - [ ' + ','.join(assignee_list) + ' ]' 

        except gidgethub.BadRequest as exc:
            print(exc.status_code)
            return "Error" + exc.status_code
    
          











