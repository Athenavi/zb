import configparser
import os

from flask import jsonify
from packaging.version import Version

from src.database import get_db
from src.models import CustomField


def theme_safe_check(theme_id, channel=1):
    theme_path = f'templates/theme/{theme_id}'
    if not os.path.exists(theme_path):
        return False
    has_index_html = os.path.exists(os.path.join(theme_path, 'index.html'))
    has_template_ini = os.path.exists(os.path.join(theme_path, 'template.ini'))

    if has_index_html and has_template_ini:
        theme_detail = configparser.ConfigParser()
        # 读取 template.ini 文件
        theme_detail.read(f'templates/theme/{theme_id}/template.ini', encoding='utf-8')
        # 获取配置文件中的属性值
        tid = theme_detail.get('default', 'id').strip("'")
        author = theme_detail.get('default', 'author').strip("'")
        theme_title = theme_detail.get('default', 'title').strip("'")
        theme_description = theme_detail.get('default', 'description').strip("'")
        author_website = theme_detail.get('default', 'authorWebsite').strip("'")
        theme_version = theme_detail.get('default', 'version').strip("'")
        theme_version_code = theme_detail.get('default', 'versionCode').strip("'")
        update_url = theme_detail.get('default', 'updateUrl').strip("'")
        screenshot = theme_detail.get('default', 'screenshot').strip("'")

        theme_properties = {
            'id': tid,
            'author': author,
            'title': theme_title,
            'description': theme_description,
            'authorWebsite': author_website,
            'version': theme_version,
            'versionCode': theme_version_code,
            'updateUrl': update_url,
            'screenshot': screenshot,
        }

        if channel == 1:
            return jsonify(theme_properties)
        else:
            # print(Version(theme_version) > Version(sys_version))
            if Version(theme_version) < Version('1.0.0'):
                return False
            else:
                return True
    else:
        return False


def get_all_themes():
    display_list = []
    themes_path = 'templates/theme'
    if os.path.exists(themes_path):
        subfolders = [f.path for f in os.scandir(themes_path) if f.is_dir()]
        for subfolder in subfolders:
            has_index_html = os.path.exists(os.path.join(subfolder, 'index.html'))
            has_template_ini = os.path.exists(os.path.join(subfolder, 'template.ini'))
            if has_index_html and has_template_ini:
                display_list.append(os.path.basename(subfolder))
    # print(display_list)
    return display_list


def db_remove_theme(user_id, theme_id):
    try:
        all_themes = get_all_themes()
        with get_db() as session:
            # 获取用户已禁用的主题列表
            custom_field = session.query(CustomField).filter_by(user_id=user_id, field_name="banThemes").first()
            ban_themes_list = custom_field.field_value.split(',') if custom_field and custom_field.field_value else []

            # 添加新的主题ID到禁用列表中
            if theme_id not in ban_themes_list:
                ban_themes_list.append(str(theme_id))

            # 如果禁用列表为空，设置为None
            ban_themes_value = ','.join(ban_themes_list) if ban_themes_list else None

            # 若用户已存在禁用主题记录，则更新；否则添加新记录
            if custom_field:
                custom_field.field_value = ban_themes_value
            else:
                custom_field = CustomField(user_id=user_id, field_name="banThemes", field_value=ban_themes_value)
                session.add(custom_field)

            session.commit()
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        session.rollback()
        return False
