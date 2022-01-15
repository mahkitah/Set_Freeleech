import os
import re
import shutil
from hashlib import sha1

from bcoding import bdecode, bencode
from gazelle_api import GazelleApi, RequestFailure

##############################################
# edit this:

torrentfolder = "D:\\Test\\Torrents"
move_on_success_folder = "D:\\Test\\Made Freeleech"  # Must exits. Use empty quotes to not move on success
api_key = "1234567890"
use_regex_for_torid = r'.+-(\d+).torrent'  # Use empty quotes to not use regex
token_size = 512 * 1024 ** 2

optimise_token_use = True  # values below are only used when this is True, set to False to disable
spend_max_tokens = 15  # 0 = no max
max_wpt = 150 * 1024 ** 2  # max waste per token, 0 = no max

###############################################

ops = GazelleApi('OPS', f'token {api_key}')

def tor_id_regex(filename):
    match = re.match(use_regex_for_torid, filename)
    if match:
        return match.group(1)

def api_tor_info(path):
    with open(path, 'rb') as f:
        dtor_dict = bdecode(f.read())
    hash = get_infohash_from_dtorrent(dtor_dict)
    return ops.request('GET', 'torrent', hash=hash)['torrent']

def get_infohash_from_dtorrent(dtor_dict):
    info = dtor_dict['info']
    return sha1(bencode(info)).hexdigest()

def waste_per_token(torrent_size, token_size):
    nr_tokens, mod = divmod(torrent_size, token_size)
    if mod:
        nr_tokens += 1
    cost = nr_tokens * token_size
    return (cost - torrent_size) / nr_tokens, nr_tokens

def scan_torrent_files(path):
    for scan in os.scandir(path):
        if scan.is_file() and scan.name.endswith('.torrent'):
            yield scan

def make_freeleech(tor_id):
    try:
        r = ops.request('GET', 'download', id=tor_id, usetoken=True)
    except RequestFailure:
        return False

    if 'application/x-bittorrent' in r.headers['content-type']:
        return True

def get_size_from_dtorrent(dtor_dict):
    size = 0
    for file in dtor_dict['info']['files']:
        size += file['length']
    return size

def main():
    if optimise_token_use:
        torrent_infos = []
        for scan in scan_torrent_files(torrentfolder):
            with open(scan.path, 'rb') as f:
                dtor_dict = bdecode(f.read())

            if use_regex_for_torid:
                tor_id = tor_id_regex(scan.name)
                tor_size = get_size_from_dtorrent(dtor_dict)
            else:
                hash = get_infohash_from_dtorrent(dtor_dict)
                tor_info = ops.request('GET', 'torrent', hash=hash)['torrent']
                tor_id = tor_info['id']
                tor_size = tor_info['size']

            wpt, nr_tokens = waste_per_token(tor_size, token_size)
            if max_wpt and wpt > max_wpt:
                continue
            torrent_infos.append((scan, tor_id, nr_tokens, wpt))

        torrent_infos.sort(key=lambda x: x[3])

        tokens_spent = 0
        for scan, tor_id, nr_tokens, _ in torrent_infos:
            if spend_max_tokens and tokens_spent + nr_tokens > spend_max_tokens:
                continue
            made_freeleech = make_freeleech(tor_id)
            if made_freeleech:
                print(f'made freeleech: {scan.name} ({nr_tokens} token{"s" if nr_tokens > 1 else ""})')
                tokens_spent += nr_tokens
                if os.path.isdir(move_on_success_folder):
                    shutil.move(scan.path, move_on_success_folder)

    else:
        for scan in scan_torrent_files(torrentfolder):
            if use_regex_for_torid:
                tor_id = tor_id_regex(scan.name)
            else:
                tor_id = api_tor_info(scan.path)['id']

            made_freeleech = make_freeleech(tor_id)
            if made_freeleech:
                print(f'made freeleech: {scan.name}')
                if os.path.isdir(move_on_success_folder):
                    shutil.move(scan.path, move_on_success_folder)

if __name__ == "__main__":
    main()
