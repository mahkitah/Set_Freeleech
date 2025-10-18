import re
import shutil
from math import ceil
from enum import Enum
from hashlib import sha1
from pathlib import Path
from typing import Iterator

from bcoding import bdecode, bencode
from gazelle_api import GazelleApi, RequestFailure

##############################################
# edit this:

torrentfolder = "D:\\Test\\Torrents\\fl_test"
move_on_success_folder = "D:\\Test\\Made Freeleech"  # Will be created if it doesn't exist. Use empty quotes not to move on success
api_key = "1234567890"
use_regex_for_torid = r'.+-(\d+).torrent'  # Use empty quotes to not use regex

optimise_token_use = True  # Torrents will be handled in order of increasing wpt, set to False to disable
# These two values below are only used when optimise_token_use is True
spend_max_tokens = 20  # 0 = no max
max_wpt = 250  # max waste per token (in MB), 0 = no max

###############################################

ops = GazelleApi('OPS', f'token {api_key}')
token_size = 320 * 1024 ** 2
max_wpt = max_wpt * 1024 ** 2
file_name_rex = re.compile(use_regex_for_torid)
comment_rex = re.compile(r'torrentid=(\d+)')

move = False
if move_on_success_folder:
    move_folder = Path(move_on_success_folder)
    try:
        move_folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print('move_on_success_folder could not be created')
        print(e)
        quit()
    move = True


def regex_id(rex: re.Pattern, txt: str) -> int | None:
    match = rex.search(txt)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def api_tor_info(dtor_dict) -> dict:
    info_hash = sha1(bencode(dtor_dict['info'])).hexdigest()
    return ops.request('GET', 'torrent', hash=info_hash)['torrent']


def waste_per_token(torrent_size: int) -> tuple[int, int]:
    nr_tokens = ceil(torrent_size / token_size)
    cost = nr_tokens * token_size
    wpt = (cost - torrent_size) / nr_tokens
    return wpt, nr_tokens


def get_tor_info(tor_path: Path):
    tor_id = None
    tor_size = None
    if use_regex_for_torid:
        tor_id = regex_id(file_name_rex, tor_path.name)

    if tor_id and not optimise_token_use:
        return tor_id

    dtor_dict: dict = bdecode(tor_path.read_bytes())
    if not tor_id:
        comment = dtor_dict.get('comment')
        if comment:
            tor_id = regex_id(comment_rex, comment)
    if not tor_id:
        tor_info = api_tor_info(dtor_dict)
        tor_id = tor_info['id']
        tor_size = tor_info['size']

    assert isinstance(tor_id, int)

    if not optimise_token_use:
        return tor_id

    if not tor_size:
        tor_size = sum(f['length'] for f in dtor_dict['info']['files'])

    wpt, nr_tokens = waste_per_token(tor_size)
    return tor_id, nr_tokens, wpt


class Result(Enum):
    Made = 'made freeleech'
    Already = 'already freeleech'
    Fail = 'failed to make freeleech'


def make_freeleech(tor_id) -> Result:
    try:
        r = ops.request('GET', 'download', id=tor_id, usetoken=True)
    except RequestFailure as e:
        if 'already freeleech' in str(e):
            return Result.Already

        return Result.Fail

    if 'application/x-bittorrent' in r.headers['content-type']:
        return Result.Made

    return Result.Fail


def not_optimised(tor_folder: Path):
    for tor_path in tor_folder.glob('*.torrent'):
        print()
        print(tor_path.name)
        tor_id = get_tor_info(tor_path)
        f_result = make_freeleech(tor_id)
        print(f_result.value)
        if f_result in (Result.Made, Result.Already) and move:
            shutil.move(tor_path, move_folder)
            print('moved')


def infos_gen(tor_folder: Path) -> Iterator[tuple[Path, int, int, int]]:
    for tor_path in tor_folder.glob('*.torrent'):
        tor_id, nr_tokens, wpt = get_tor_info(tor_path)
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

        f_result = make_freeleech(tor_id)
        print(f_result.value, end='')
        if f_result is Result.Fail:
            print()
            continue
        if f_result is Result.Already:
            print()
        elif f_result is Result.Made:
            print(f': ({nr_tokens} token{"s" if nr_tokens > 1 else ""}, wpt={round(wpt / 1024 ** 2, 2)})')
            tokens_spent += nr_tokens
        if move:
            shutil.move(tor_path, move_folder)
            print('moved')
        if spend_max_tokens and tokens_spent == spend_max_tokens:
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
