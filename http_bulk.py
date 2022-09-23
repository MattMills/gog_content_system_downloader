import sys
import os
import time
import requests
import zlib
import hashlib
from auth import auth
from concurrent.futures import ThreadPoolExecutor, as_completed

class http_bulk:
    def __init__(self, auth=None):
        if auth is None:
            raise Exception('http module initialized with no auth param')

        self.auth = auth
        self.s = requests.Session()
        self.thread_limit = 50
        self.queue = []
        self.running_queue = None

        self.stats = {}
        self.stats['success_chunks'] = 0
        self.stats['chunk_retry'] = 0
        self.stats['fail_chunks'] = 0
        self.stats['existing_chunks'] = 0

        self.timing = time.time()
        self.session = requests.Session()

    def runner(self):
        threads= []
        self.running_queue = self.queue
        self.queue = []

        with ThreadPoolExecutor(max_workers=self.thread_limit) as executor:
            for entry in self.running_queue:
                threads.append(executor.submit(self.download_file, entry))

        self.running_queue = None
        print('http_bulk queue commplete, %s' % (self.stats,))

    def queue_file(self, file_meta):
        self.queue.append(file_meta)


    def download_file(self, file_meta):
        fail_file = False
        with open(file_meta['file_path'], 'wb') as fh:
            for chunk in file_meta['chunks']:
                chunk_url = self.auth.get_secure_link(file_meta['productId'])
                chunk_url += '/%s/%s/%s' % (chunk['compressedMd5'][0:2], chunk['compressedMd5'][2:4], chunk['compressedMd5'])

                fail_chunk = True
                for attempts in range(0,5):
                    if attempts > 0:
                        self.stats['chunk_retry'] += 1
                    try:
                        resp = self.session.get(chunk_url)
                    except Exception as e:
                        print ('ERR exception while fetching chunk (attempt #%s) %s %s' % (attempts, type(e), e))
                        continue
                    
                    if resp.status_code != 200:
                        print ('ERR non-200 status code on chunk (attempt #%s) %s %s' % (attempts, resp.status_code, resp.headers))
                        continue

                    zlib_obj = zlib.decompressobj()
                    md5sum = hashlib.md5(resp.content).hexdigest()

                    if md5sum != chunk['compressedMd5']:
                        print ('ERR chunk MD5 does not match (attempt #%s) %s != %s' % (attempts, chunk['compressedMd5'], md5sum))
                        continue

                    fh.write(zlib_obj.decompress(resp.content))
                    fail_chunk = False
                    break
                if fail_chunk == True:
                    #We've hit max retries and failed to get the chunk.
                    fail_file = True
                    break

        if fail_file == True:
            try:
                os.remove(file_meta['file_path'])
            except:
                pass
            print('file write fail, %s' % (file_meta['path']))
            self.stats['fail_chunks'] += len(file_meta['chunks'])
        else:
            print('file write complete, %s bytes\t%s' % (os.path.getsize(file_meta['file_path']), file_meta['path']))
            self.stats['success_chunks'] += len(file_meta['success_chunks'])

