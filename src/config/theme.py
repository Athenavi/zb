import configparser
import os

from flask import jsonify
from packaging.version import Version

from src.database import SessionLocal
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
    display_list = ['default']
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

def db_change_theme(user_id, theme_id):
    try:
        session = SessionLocal()
        
        new_theme = CustomField(user_id=user_id, field_name="theme", field_value=str(theme_id))
        session.add(new_theme)
        session.commit()
        
        session.close()
        return True
    except Exception:
        session.rollback()
        session.close()
        return False


def db_get_theme():
    try:
        session = SessionLocal()
        
        theme_record = session.query(CustomField.field_value).filter(
            CustomField.user_id == 1,
            CustomField.field_name == 'theme'
        ).order_by(CustomField.id.desc()).first()
        
        session.close()
        current_theme = theme_record[0] if theme_record else 'default'
    except Exception as e:
        session.rollback()
        session.close()
        print(f"Error getting current theme: {e}")
        current_theme = 'default'
    return str(current_theme)
