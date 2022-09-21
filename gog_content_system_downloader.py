import requests
import json
import os
import sys
import time
import zlib
import hashlib
from auth import auth


manifest_dir = 'build_manifests/'
download_dir = '/zpool0/share/stellaris_backups_gog/'
base_meta_url = 'https://gog-cdn-lumen.secure2.footprint.net/content-system/v2/meta/'
prefix_secure_url = 'https://content-system.gog.com/products/' #product ID will be inserted here in the code
suffix_secure_url = '/secure_link?generation=2&path=/&_version=2'


allowed_product_ids = ['1508702879']


#products.json -> build
#{
#  "branch": null,
#  "date_published": "2022-06-27T07:09:57+00:00",
#  "generation": 2,
#  "id": 55566076607633620,
#  "legacy_build_id": null,
#  "link": "https://gog-cdn-lumen.secure2.footprint.net/content-system/v2/meta/0b/43/0b43fa92db60cfd868f5a078f2d94f23",
#  "listed": true,
#  "meta_id": "0b43fa92db60cfd868f5a078f2d94f23",
#  "os": "osx",
#  "product_id": 1508702879,
#  "public": true,
#  "tags": [
#    "csb_10_6_1_l_158"
#  ],
#  "version": "3.4.5"
#}


s = requests.Session()
a = auth()

with open('product.json', 'r') as fh:
    product = json.load(fh)

builds_by_buildid = {}
for build in product['builds']:
    builds_by_buildid[str(build['id'])] = build

seen_build_ids = []

dirs = os.listdir(manifest_dir)
for this_file in dirs:
    with open('%s/%s' % (manifest_dir, this_file), 'r') as fh:
        manifest = json.load(fh)

        build_id = manifest['buildId']
        seen_build_ids.append(build_id)
        
        try:
            platform = builds_by_buildid[build_id]['os']
            version = builds_by_buildid[build_id]['version']
        except Exception as e:
            print('%s\tExcept: %s - %s' % (build_id, type(e), e))
            continue

        depot_count = 0
        depot_existing = 0
        depot_dl_success = 0
        depot_dl_fail = 0
        for depot in manifest['depots'] + [manifest['offlineDepot']]: #Not sure why these are structured seperately, but I want all.
            depot_count += 1
            if(os.path.isfile('%s/%s/%s/manifest/%s' % (download_dir, version, platform, depot['manifest']))):
                    #manifest already in cache, use that version
                    with open('%s/%s/%s/manifest/%s' % (download_dir, version, platform, depot['manifest']), 'r') as fh2:
                        depot_manifest_data = fh2.read()
                        depot_existing += 1
            else:
                url = '%s%s/%s/%s' % (base_meta_url, depot['manifest'][0:2], depot['manifest'][2:4], depot['manifest'])
                r = s.get(url)

                if(r.status_code != 200):
                    print('ERR RESPONSE %s URL: %s' % (r.status_code, url,))
                    depot_dl_fail += 1
                    continue
                else:
                    zlib_obj = zlib.decompressobj()
                    md5sum = hashlib.md5(r.content).hexdigest()
                    depot_manifest_data = zlib_obj.decompress(r.content).decode('utf-8')
                    if md5sum != depot['manifest']:
                        print('ERR depot manifest md5 mismatch for %s - (%s) got %s bytes' % (depot['manifest'], md5sum, len(r.content)))
                        depot_dl_fail +=  1
                        continue

                os.makedirs('%s/%s/%s/manifest/' % (download_dir, version, platform), exist_ok=True)
                with open('%s/%s/%s/manifest/%s' % (download_dir, version, platform, depot['manifest']), 'w') as fh2:
                    fh2.write(depot_manifest_data)
                    depot_dl_success += 1

            is_gog_depot = ('isGogDepot' in depot and depot['isGogDepot'])
                
            download_path = '%s/%s/%s/%s' % (download_dir, version, platform, ('gog_depots' if is_gog_depot else 'depots'))
            os.makedirs(download_path, exist_ok=True)
            try:
                depot_manifest_json = json.loads(depot_manifest_data)
            except Exception as e:
                print('ERR exception during json.loads of depot_manifest_data %s %s' % (type(e), e))
                continue

            small_file_refs = []

            for item in depot_manifest_json['depot']['items']:
                item['path'] = item['path'].replace("\\", '/')
                file_path = '%s/%s' % (download_path, item['path'])
                dir_path = os.path.dirname(file_path)
                os.makedirs(dir_path, exist_ok=True)

                if 'sfcRef' in item: #save these for later, small file container is defined at the depot level
                    small_file_refs.append(item)
                    continue

                if os.path.isfile(file_path):
                    #file already exists, check hash and continue or delete
                    # -- TODO: don't have a hash yet, that's in one of the depots... 
                    # but we can check size?
                    expected_size = sum(chunk['size'] for chunk in item['chunks'])
                    file_size = os.path.getsize(file_path)
                    if file_size != expected_size:
                        print('ERR Incorrect filesize - %s expected %s actual %s' % (file_path, expected_size, file_size))
                        os.remove(file_path)
                    else:
                        #File size is correct, so skip file, we'll check hashes somewhere else since I left the hashes in one of these boxes.
                        continue
                if depot['productId'] not in allowed_product_ids:
                    print('Unlicensed product - skipping %s' %file_path)
                    continue

                fail = False
                with open(file_path, 'wb') as item_fh:
                    for chunk in item['chunks']:
                        #download file chunks and put them together
                        chunk_url = a.get_secure_link(depot['productId']) #not sure this is right...
                        chunk_url += '/%s/%s/%s' % (chunk['compressedMd5'][0:2], chunk['compressedMd5'][2:4], chunk['compressedMd5'])
                        try:
                            resp = s.get(chunk_url)
                        except Exception as e:
                            print ('ERR exception while fetching chunk %s %s' % (type(e), e))
                            fail = True
                            break

                        if(resp.status_code != 200):
                            print('ERR non-200 status code on chunk %s %s' % (resp.status_code, resp.headers))
                            fail = True
                            break

                        zlib_obj = zlib.decompressobj()
                        md5sum = hashlib.md5(resp.content).hexdigest()
                        if(md5sum != chunk['compressedMd5']):
                            print('ERR Chunk compressedMd5 did not match expected: %s, seen: %s' % (chunk['compressedMd5'], md5sum))
                            fail = True
                            break

                        item_fh.write(zlib_obj.decompress(resp.content))


                if fail == True:
                    os.remove(file_path)
                    print('file write fail, %s' % (item['path']))
                else:
                    print('file write complete, %s\t%s' % (os.path.getsize(file_path), item['path']))
            #deal with small file refs
            
            #sfc = depot_manifest_json['smallFilesContainer']
#{
#      "path": "gfx\\interface\\fleet_view\\GFX_rallypoint_toggle_on_large.dds",
#      "chunks": [
#        {
#          "md5": "7649f0eb6d20ac9a73570ab8a20e2af7",
#          "size": 32576,
#          "compressedMd5": "506f99904ae2901f51b3a47fa828fb96",
#          "compressedSize": 14792
#        }
#      ],
#      "type": "DepotFile",
#      "sfcRef": {
#        "offset": 130304,
#        "size": 32576
#      }
#    },
#  {
#    "path": "pdx_browser\\locales\\vi.pak",
#    "chunks": [
#      {
#        "md5": "44572ba5814c909a6202c7da42ea6c28",
#        "size": 230074,
#        "compressedMd5": "15dcfef57e7f8b725bc9f091be93eeef",
#        "compressedSize": 66484
#      }
#    ],
#    "type": "DepotFile"
#  },
          #"smallFilesContainer"



        print('%s\t%s\t%s\ttotal: %s existing: %s dl_success: %s dl_fail: %s' % (build_id, platform, version, depot_count, depot_existing, depot_dl_success, depot_dl_fail))


for build in product['builds']:
    if str(build['id']) not in seen_build_ids:
        print ('ERR: Build ID in product but not manifests: %s' % (build['id'],))





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

        self.token_acquire_timestamp = None
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


    # get a secure link for a product_id from cache or request a new one, this should be used for 
    def get_secure_link(self, product_id, index=0):
        if product_id not in self.secure_links:
            self.secure_links[product_id] = self.request_secure_link(product_id)
        if self.secure_links[product_id]['urls'][index]['parameters']['expires_at'] > time.time()-self.secure_link_expire_allowance:
            del self.secure_links[product_id] #clear it in case the next line throws an exception
            self.secure_links[product_id] = self.request_secure_link(product_id)
        
        sl = self.secure_links[product_id]['urls'][index]
        url = sl['url_format']
        for key, parameter in parameters:
            url.replace('{%s}' % (key,), parameter)

        return url

    def request_secure_link(self, product_id):
        self.setup_auth_header()
        url = '%s%s%s' % (prefix_secure_url, product_id, suffix_secure_url)
        response = s.get(url)
        if(response.status_code == 200):
            return response.content
        else:
            raise Exception('Error while requesting secure link response code %s, body: %s' % (response.status_code, response.content))

        
