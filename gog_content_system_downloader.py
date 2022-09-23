import requests
import json
import os
import sys
import time
import zlib
import hashlib
from auth import auth
from http_bulk import http_bulk


# The root directory to download into, depots will be stored by their OS and Version string:
# download_dir/1.0.0/windows/manifest/
# download_dir/1.0.0/windows/depots/
# download_dir/1.0.0/windows/gog_depots/
download_dir = '/zpool0/share/stellaris_backups_gog/'

# GOG product IDs that should be downloaded (must be licensed on your account)
allowed_product_ids = ['1508702879',]


manifest_dir = 'build_manifests/'
base_meta_url = 'https://gog-cdn-lumen.secure2.footprint.net/content-system/v2/meta/'
prefix_secure_url = 'https://content-system.gog.com/products/' #product ID will be inserted here in the code
suffix_secure_url = '/secure_link?generation=2&path=/&_version=2'




s = requests.Session()
a = auth()
http_bulk = http_bulk(a)

if os.path.isfile('product.json'):
    with open('product.json', 'r') as fh:
        product = json.load(fh)
else:
    raise Exception('No product.json file, read README')

if not os.path.isdir(manifest_dir):
    raise Exception('No build_manifests dir, read README')


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
        for depot in manifest['depots']:
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

                item['productId'] = depot['productId']
                item['file_path'] = file_path

                http_bulk.queue_file(item)

            http_bulk.runner()
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

