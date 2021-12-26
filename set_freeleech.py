import os
from hashlib import sha1

from bcoding import bdecode, bencode
from gazelle_api import GazelleApi

torrentfolder = "D:\\Test\\Torrents"
api_key = "1234567890"

###############################################

ops = GazelleApi('OPS', api_key)

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
            ops.request('GET', 'download', expect_bytes=True, id=tor_id, usetoken=True)
