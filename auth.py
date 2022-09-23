import requests
import json
import time
import os

prefix_secure_url = 'https://content-system.gog.com/products/' #product ID will be inserted here in the code
suffix_secure_url = '/secure_link?generation=2&path=/&_version=2'
auth_renewal_url =  'https://auth.gog.com/token'

auth_token_file = 'gog_token.json'



class auth:

    def __init__(self):
        global auth_token_file
        # Not sure where these two are from, seems to work, using per https://gogapidocs.readthedocs.io/en/latest/auth.html
        # (which is unofficial docs)
        self.client_id = '46899977096215655'
        self.client_secret = '9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9'


        self.current_token = {
                'access_token': None,
                'expires_in': None,
                'token_type': None,
                'scope': None,
                'session_id': None,
                'refresh_token': None,
                'user_id': None,
                }

        if os.path.isfile(auth_token_file):
            with open(auth_token_file, 'r') as fh:
                self.current_token = json.load(fh)
            if 'access_token' not in self.current_token:
                raise Exception('ERR: file %s contains invalid/missing auth_token field' % (auth_token_file,))
            if 'expires_in' not in self.current_token:
                raise Exception('ERR: file %s contains invalid/missing expires_in field' % (auth_token_file,))
            if 'refresh_token' not in self.current_token:
                raise Exception('ERR: file %s contains invalid/missing refresh_token field' % (auth_token_file,))
        else:
            raise Exception('ERR: file %s not found, read README for instructions' % (auth_token_file,))

        self.secure_links = {}

        self.token_acquire_timestamp = time.time()-1800 # since the token doesn't include a timestamp, we'll just assume you got it less than 30 min ago.
        self.token_expire_allowance = 30 #seconds
        self.secure_link_expire_allowance = 5 #seconds
        self.session = requests.Session()

    def get_current_token(self):
        if(self.token_acquire_timestamp != None and time.time()-self.token_acquire_timestamp > self.current_token['expires_in']-self.token_expire_allowance):
            return self.current_token['access_token']
        else:
            self.current_token = self.renew_current_token()
            return self.current_token['access_token']

    def setup_auth_header(self):
        self.session.headers.update({'Authorization': 'Bearer %s' % (self.get_current_token(),)})
        self.session.headers.update({'User-Agent': 'GOGGalaxyClient/1.2.17.9 gogdl/1.0'})


    # get a secure link for a product_id from cache or request a new one, this should be used for 
    def get_secure_link(self, product_id, index=0):
        if product_id not in self.secure_links:
            self.secure_links[product_id] = self.request_secure_link(product_id)
        if self.secure_links[product_id]['urls'][index]['parameters']['expires_at'] > time.time()-self.secure_link_expire_allowance:
            del self.secure_links[product_id] #clear it in case the next line throws an exception
            self.secure_links[product_id] = self.request_secure_link(product_id)
        
        sl = self.secure_links[product_id]['urls'][index]
        url = sl['url_format']
        for key, parameter in sl['parameters'].items():
            url = url.replace('{%s}' % (key,), str(parameter))

        return url

    def request_secure_link(self, product_id):
        global prefix_secure_url, suffix_secure_url

        self.setup_auth_header()
        url = '%s%s%s' % (prefix_secure_url, product_id, suffix_secure_url)
        response = self.session.get(url)
        if(response.status_code == 200):
            return json.loads(response.content)
        else:
            raise Exception('Error while requesting secure link response code %s, body: %s' % (response.status_code, response.content))

    def renew_current_token(self):
        global auth_renewal_url, auth_token_file
        if self.current_token['refresh_token'] == None:
            raise Exception('Tried to renew current token without a valid refresh token')

        url = '%s?client_id=%s&client_secret=%s&refresh_token=%s&grant_type=refresh_token' % (auth_renewal_url, self.client_id, self.client_secret, self.current_token['refresh_token'])

        response = self.session.get(url)
        if(response.status_code == 200):
            with open(auth_token_file, 'w') as fh:
                fh.write(response.content.decode('utf-8'))
            self.token_acquire_timestamp = time.time()
            return json.loads(response.content)
        else:
            raise Exception('Error while refreshing auth token, response code %s, body: %s' % (response.status_code, response.content))

        
