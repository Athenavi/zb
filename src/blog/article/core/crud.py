from src.blog.article.core.content import get_i18n_title
from src.utils.security.safe import is_valid_iso_language_code


def get_blog_name(aid, i18n_code=None):
    # 此函数逻辑不变，仍使用原有的get_i18n_title函数
    i180_title = None
    try:
        if i18n_code:
            if not is_valid_iso_language_code(i18n_code):
                return None
            i180_title = get_i18n_title(iso=i18n_code, aid=aid)
        return i180_title
    except Exception:
        return i180_title
