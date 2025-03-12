import os
import re
import shutil
from math import ceil
from hashlib import sha1
from pathlib import Path
from typing import Iterator

from bcoding import bdecode, bencode
from gazelle_api import GazelleApi, RequestFailure

##############################################
# edit this:

torrentfolder = "D:\\Test\\Torrents\\fl_test"
move_on_success_folder = "D:\\Test\\Made Freeleech"  # Must exist. Use empty quotes to not move on success
api_key = "1234567890"
use_regex_for_torid = r'.+-(\d+).torrent'  # Use empty quotes to not use regex

optimise_token_use = True  # values below are only used when this is True, set to False to disable
spend_max_tokens = 15  # 0 = no max
max_wpt = 150  # max waste per token (in MB), 0 = no max

###############################################

ops = GazelleApi('OPS', f'token {api_key}')
token_size = 512 * 1024 ** 2
max_wpt = max_wpt * 1024 ** 2


def tor_id_regex(filename: str) -> int:
    match = re.match(use_regex_for_torid, filename)
    if match:
        return int(match.group(1))


def api_tor_info(dtor_dict) -> dict:
    info_hash = sha1(bencode(dtor_dict['info'])).hexdigest()
    return ops.request('GET', 'torrent', hash=info_hash)['torrent']


def waste_per_token(torrent_size: int) -> tuple[int, int]:
    nr_tokens = ceil(torrent_size / token_size)
    cost = nr_tokens * token_size
    wpt = (cost - torrent_size) / nr_tokens
    return wpt, nr_tokens


def make_freeleech(tor_id) -> bool:
    try:
        r = ops.request('GET', 'download', id=tor_id, usetoken=True)
    except RequestFailure:
        return False

    if 'application/x-bittorrent' in r.headers['content-type']:
        return True


def not_optimised(tor_folder: Path):
    for tor_path in tor_folder.glob('*.torrent'):
        print()
        print(tor_path.name)
        if use_regex_for_torid:
            tor_id = tor_id_regex(tor_path.name)
        else:
            dtor_dict = bdecode(tor_path.read_bytes())
            tor_id = api_tor_info(dtor_dict)['id']

        made_freeleech = make_freeleech(tor_id)
        if made_freeleech:
            print('made freeleech')
            if os.path.isdir(move_on_success_folder):
                shutil.move(tor_path, move_on_success_folder)


def infos_gen(tor_folder: Path) -> Iterator[tuple[Path, int, int, int]]:
    if not use_regex_for_torid:
        print('Getting torrent id\'s from api. This could take a while')
    for tor_path in tor_folder.glob('*.torrent'):
        dtor_dict: dict = bdecode(tor_path.read_bytes())
        if use_regex_for_torid:
            tor_id = tor_id_regex(tor_path.name)
            tor_size = sum(f['length'] for f in dtor_dict['info']['files'])
        else:
            tor_info = api_tor_info(dtor_dict)
            tor_id = tor_info['id']
            tor_size = tor_info['size']
            print(tor_id)

        wpt, nr_tokens = waste_per_token(tor_size)
        yield tor_path, tor_id, nr_tokens, wpt


def optimised(tor_folder: Path):
    tokens_spent = 0
    for tor_path, tor_id, nr_tokens, wpt in sorted(infos_gen(tor_folder), key=lambda x: x[3]):
        print()
        print(tor_path.name)
        if max_wpt and wpt > max_wpt:
            print(f'skipped: wpt({round(wpt / 1024 ** 2, 2)}) > max')
            continue
        if spend_max_tokens and tokens_spent + nr_tokens > spend_max_tokens:
            print(f'skipped: {nr_tokens} tokens would exceed max tokens spent')
            continue

        made_freeleech = make_freeleech(tor_id)
        if made_freeleech:
            print(f'made freeleech: {tor_path.name} ({nr_tokens} token{"s" if nr_tokens > 1 else ""})')
            tokens_spent += nr_tokens
            if os.path.isdir(move_on_success_folder):
                shutil.move(tor_path, move_on_success_folder)
            if tokens_spent == spend_max_tokens:
                print('stopping: max tokens reached')
                break


def main():
    tor_folder = Path(torrentfolder)
    if optimise_token_use:
        optimised(tor_folder)
    else:
        not_optimised(tor_folder)


if __name__ == "__main__":
    main()
