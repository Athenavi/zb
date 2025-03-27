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


def filter_sensitive_words(comment_content):
    sensitive_words = ['违禁词1', '违禁词2', '敏感词1', '敏感词2']

    comment_content_lower = comment_content.lower()
    for word in sensitive_words:
        if word in comment_content_lower:
            return False

    return True
