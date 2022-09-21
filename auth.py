import requests
import json
import time

prefix_secure_url = 'https://content-system.gog.com/products/' #product ID will be inserted here in the code
suffix_secure_url = '/secure_link?generation=2&path=/&_version=2'


class auth:

    def __init__(self):
        self.current_token = {
                'access_token': None,
                'expires_in': None,
                'token_type': None,
                'scope': None,
                'session_id': None,
                'refresh_token': None,
                'user_id': None,
                }
        self.secure_links = {}

        self.token_acquire_timestamp = time.time()-3600
        self.token_expire_allowance = 30 #seconds
        self.secure_link_expire_allowance = 5 #seconds
        self.session = requests.Session()

    def get_current_token(self):
        if(self.token_acquire_timestamp != None and time.time()-self.token_acquire_timestamp > self.current_token['expires_in']-self.token_expire_allowance):
            return self.current_token['access_token']
        else:
            #todo: Acquire a token?
            raise Exception('Missing a valid auth token (not set or expired)')

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

        
