import re


def run_security_checks(url):
    pattern = r"^(https?://)?([a-zA-Z0-9-]+\.)*[a-zA-Z]{2,}(\/)$"
    if re.match(pattern, url):
        return True
    else:
        return False


def clean_html_format(text):
    clean_text = re.sub('<.*?>', '', str(text))
    return clean_text
