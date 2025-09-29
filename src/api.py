# SPDX-License-Identifier: MIT

import json
import requests
from retry import retry

from collections.abc import Callable
from datetime import datetime, timezone

class ApiHelper:
    def __init__(self,
                 device_idfv: str,
                 device_id: str,
                 access_token: str,
                 refresh_token: str,
                 token_refresh_callback: Callable[[dict], None] = None):
        self.session: requests.Session = requests.Session()
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_refresh_callback = token_refresh_callback
        
        self.req_headers = {
            'user-agent': 'Xiaoyuzhou/2.94.0 (build:2749; iOS 18.6.2)',
            'market': 'AppStore',
            'x-jike-device-properties': json.dumps({
                "idfv": device_idfv,
                "idfa": "00000000-0000-0000-0000-000000000000"
            }, separators=(',', ':')),
            'app-buildno': '2749',
            'x-jike-device-id': device_id,
            'os': 'ios',
            'x-custom-xiaoyuzhou-app-dev': '',
            'manufacturer': 'Apple',
            'bundleid': 'app.podcast.cosmos',
            'abtest-info': '{}',
            'accept-language': 'en-US;q=1.0',
            'x-online-host': 'api.xiaoyuzhoufm.com', # not in refresh
            'timezone': 'Asia/Shanghai',
            'model': 'iPhone17,1',
            'app-permissions': '100000',
            'accept': '*/*',
            'app-version': '2.94.0',
            'os-version': '18.6.2',
            'wificonnected': 'true',
            # 'accept-encoding': 'br;q=1.0, gzip;q=0.9, deflate;q=0.8',
        }


    @staticmethod
    def get_local_time():
        return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


    def get_common_req_header(self):
        return {
            **self.req_headers,
            'x-jike-access-token': self.access_token,
            'local-time': self.get_local_time(),
        }

    @retry(requests.exceptions.ConnectionError, tries=6, delay=15)
    def api_get(self, url: str, headers: dict={}):
        token_refreshed = False
        while not token_refreshed:
            headers = {
                **self.get_common_req_header(),
                **headers,
            }
            r = self.session.get(url, headers=headers)
            if r.status_code == 401:
                self.refresh_access_token()
                token_refreshed = True
                continue
            elif r.status_code != 200:
                raise Exception(f'Invalid response status code: {r.status_code}')

            return r.json()
        raise Exception('Authentication failed')

    @retry(requests.exceptions.ConnectionError, tries=6, delay=15)
    def api_post(self, url: str, post_data: dict={}):
        token_refreshed = False
        post_data = json.dumps(post_data)
        while True:
            headers = {
                **self.get_common_req_header(),
                'content-type': 'application/json',
            }
            r = self.session.post(url, post_data, headers=headers)
            if r.status_code == 401:
                if token_refreshed:
                    break
                self.refresh_access_token()
                token_refreshed = True
                continue
            elif r.status_code != 200:
                raise Exception(f'Invalid response status code: {r.status_code}')

            return r.json()
        raise Exception('Authentication failed')


    def refresh_access_token(self):
        headers = {
            **self.get_common_req_header(),
            'x-jike-refresh-token': self.refresh_token,
        }
        r = self.session.get('https://api.xiaoyuzhoufm.com/app_auth_tokens.refresh', headers=headers)
        if r.status_code != 200:
            raise Exception(f'Failed to refresh access_token: {r.status_code}')
        res = r.json()
        if res.get('success', False):
            self.access_token = res.get('x-jike-access-token', '')
            self.refresh_token = res.get('x-jike-refresh-token', '')
        else:
            raise Exception(f'Failed to refresh access_token: success is not true')
        if self.token_refresh_callback is not None:
            self.token_refresh_callback(res)


    def get_podcast(self, pid):
        return self.api_get(f'https://api.xiaoyuzhoufm.com/v1/podcast/get?pid={pid}')


    def list_episode(self, pid, order='desc', limit=20, load_more_key=None):
        post_data = {
            "pid": pid,
            "order": order,
            "limit": limit
        }
        if load_more_key is not None:
            post_data['loadMoreKey'] = load_more_key
        res = self.api_post('https://api.xiaoyuzhoufm.com/v1/episode/list', post_data=post_data)
        return res


    def get_episode(self, eid):
        return self.api_get(f'https://api.xiaoyuzhoufm.com/v1/episode/get?eid={eid}')


    def list_comment_primary(self, eid, order='hot', load_more_key=None):
        """
        order='hot' or ...
        """
        post_data = {
            "owner": {
                "type": "EPISODE",
                "id": eid,
            },
            "order": order.upper(),
        }
        if load_more_key is not None:
            post_data['loadMoreKey'] = load_more_key
        res = self.api_post('https://api.xiaoyuzhoufm.com/v1/comment/list-primary', post_data=post_data)
        return res

    def list_comment_thread(self, primary_comment_id, order='smart', load_more_key=None):
        """
        order='smart' or 'time'
        """
        post_data = {
            "primaryCommentId": primary_comment_id,
            "order": order.upper(),
        }
        if load_more_key is not None:
            post_data['loadMoreKey'] = load_more_key
        res = self.api_post('https://api.xiaoyuzhoufm.com/v1/comment/list-thread', post_data=post_data)
        return res
