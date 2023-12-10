import requests
import json
import os
import sys
import time
import zlib

product_id = '1508702879'


manifest_dir = 'build_manifests/'

product_url_prefix = 'https://www.gogdb.org/data/products/'

headers = {}

if os.path.isfile('product.json'):
    modified_time = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime(os.path.getmtime('product.json')))
    print('Existing product.json found, last modified time: %s' % (modified_time,))

    headers = {'If-Modified-Since': modified_time}

    

r = requests.get('%s%s/product.json' % (product_url_prefix, product_id), headers=headers)
if r.status_code == 304:
    print('Received 304 not modified, exiting')
    exit()
elif r.status_code != 200:
    print('ERROR: Abnormal status code: %s ' % r.status_code)  
    print(r.headers)
    print(r.text)
    exit()
else:
    #status code == 200
    with open('product.json', 'w') as fh:
        fh.write(r.text)
    modified_time = r.headers['Last-Modified']
    print('Updated product.json: %s' % modified_time)
    mtime = time.mktime(time.strptime(modified_time, '%a, %d %b %Y %H:%M:%S %Z'))

    os.utime('product.json', (mtime, mtime))
        

#product_json = json.loads(r.text)
fh = open('product.json')
product_json = json.load(fh)
fh.close()

stat = {}
stat['total'] = 0
stat['existing'] = 0
stat['downloaded'] = 0
stat['failed'] = 0

for build in product_json['builds']:
    stat['total'] += 1
    if(os.path.isfile('%s%s.json' % (manifest_dir, build['id']))):
        stat['existing'] += 1
    else:
        r = requests.get(build['link'])
        if(r.status_code == 200):
            file_content = zlib.decompress(r.content, wbits=15).decode("utf-8")
            with open('%s%s.json' % (manifest_dir, build['id']), 'w') as fh:
                fh.write(file_content)
            modified_time = r.headers['Last-Modified']
            mtime = time.mktime(time.strptime(modified_time, '%a, %d %b %Y %H:%M:%S %Z'))
            os.utime('%s%s.json' % (manifest_dir, build['id']), (mtime, mtime))
            stat['downloaded'] += 1
            print('Updated build manifest for build %s datetime %s' % (build['id'], modified_time))
        else:
            print('ERROR: Abnormal status code %s for build %s manifest' % (r.status_code, build['id']))
            stat['failed'] += 1

print('Manifest update process complete')
print('stats: %s' % (stat,))
