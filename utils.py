import time
import urllib.request
import ssl

def urlopen_to_file(logger, url, filename, retries = 0):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for i in range(retries + 1):
        try:
            with urllib.request.urlopen(url, context=ctx) as u, open(filename, 'wb') as f:
                f.write(u.read())
            return
        except Exception as err:
            if i < retries:
                sleep = i * 2
                logger.warning(f"Failed to fetch from url {url}, retrying after {sleep}s: {err}")
                time.sleep(sleep)
            else:
                logger.error(f"Failed to fetch from url {url}: {err}")
