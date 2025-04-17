import random
import re
import string


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


def random_string(param):
    return ''.join(random.sample(string.ascii_letters + string.digits, param))


def is_valid_hash(length, f_hash):
    """
    验证哈希值是否为指定长度的十六进制字符串
    :param length: 哈希值的预期长度
    :param f_hash: 哈希值字符串
    :return: 如果哈希值有效则返回 True，否则返回 False
    """
    if f_hash is None or not isinstance(f_hash, str) or len(f_hash) != length or not all(
            c in '0123456789abcdef' for c in f_hash.lower()):
        return False
    return True


def generate_random_text():
    # 生成随机的验证码文本
    characters = list('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
    captcha_text = ''.join(random.choices(characters, k=4))
    return captcha_text
