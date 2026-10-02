import requests
from requests.adapters import HTTPAdapter

from oas.ext.path.atomic import atomic_write, atomic_write_stream, file_write_stream


class Downloader:
    def new_session(self):
        session = requests.Session()
        session.trust_env = False
        session.mount('http://', HTTPAdapter(max_retries=3))
        session.mount('https://', HTTPAdapter(max_retries=3))

        proxies = {'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}
        session.proxies = proxies
        # session.headers['User-Agent'] = self.user_agent
        return session

    def atomic_download(self, url: str, file: str):
        """
        Download a file from url then write into file
        """
        session = self.new_session()
        resp = session.get(url)
        resp.raise_for_status()

        content = resp.content
        atomic_write(file, content)
        return content

    def file_download_stream(self, url: str, file: str, chunk_size=8192):
        """
        Download a file from url then write file in stream.
        Usually to be used to download a large file, so content don't return in memory
        """
        session = self.new_session()
        resp = session.get(url, stream=True)

        content = resp.iter_content(chunk_size=chunk_size)
        file_write_stream(file, content)

    def atomic_download_stream(self, url: str, file: str, chunk_size=8192):
        """
        Download a file from url then write file in stream.
        Usually to be used to download a large file, so content don't return in memory
        """
        session = self.new_session()
        resp = session.get(url, stream=True)

        content = resp.iter_content(chunk_size=chunk_size)
        atomic_write_stream(file, content)
