import os
import shutil
from hashlib import sha1

from bcoding import bdecode, bencode
from gazelle_api import GazelleApi

##############################################
# edit this:

torrentfolder = "D:\\Test\\Torrents"
move_on_success_folder = "D:\\Test\\Made Freeleech"
api_key = "1234567890"

###############################################

ops = GazelleApi('OPS', f'token {api_key}')

def get_infohash_from_dtorrent(torrent):
    torrent = bdecode(torrent)
    info = torrent['info']
    return sha1(bencode(info)).hexdigest()

def get_torid_from_hash(hash):
    r = ops.request('GET', 'torrent', hash=hash)
    return r['torrent']['id']

if __name__ == "__main__":
    for scan in os.scandir(torrentfolder):
        if scan.is_file() and scan.name.endswith('.torrent'):
            with open(scan.path, 'rb') as f:
                torbytes = f.read()
            hash = get_infohash_from_dtorrent(torbytes)
            tor_id = get_torid_from_hash(hash)
            r = ops.request('GET', 'download', id=tor_id, usetoken=True)

            if os.path.isdir(move_on_success_folder):
                if 'application/x-bittorrent' in r.headers['content-type']:
                    shutil.move(scan.path, move_on_success_folder)
