import re

def zb_safe_check(url):
    pattern = r"^(https?://)?([a-zA-Z0-9-]+\.)*[a-zA-Z]{2,}(\/)$"
    if re.match(pattern, url):
        return True
    else:
        return False