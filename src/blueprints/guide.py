import os
import secrets
import string
import psycopg2
from mysql.connector import connect as mysql_connect
from sqlite3 import connect as sqlite_connect
from flask import Blueprint, render_template, request, jsonify, current_app

guide_bp = Blueprint('guide', __name__)


def skip_auth(f):
    f._skip_auth = True
    return f


@guide_bp.before_app_request
def check_auth():
    """在请求前检查是否需要跳过认证"""
    if request.endpoint and hasattr(current_app.view_functions[request.endpoint], '_skip_auth'):
        return  # 跳过认证


class GuideConfig:
    """引导配置类"""

    def __init__(self):
        self.steps = [
            {'id': 'welcome', 'title': '欢迎', 'description': '系统初始化引导'},
            {'id': 'database', 'title': '数据库', 'description': '数据库连接配置'},
            {'id': 'app', 'title': '应用配置', 'description': '基础应用设置'},
            {'id': 'admin', 'title': '管理员', 'description': '创建管理员账户'},
            {'id': 'optional', 'title': '可选配置', 'description': '其他功能配置'},
            {'id': 'complete', 'title': '完成', 'description': '系统初始化完成'}
        ]

    @staticmethod
    def generate_secret_key(length=32):
        """生成安全的 SECRET_KEY"""
        alphabet = string.ascii_letters + string.digits + '!@#$%^&*()_+-='
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def test_database_connection(db_config):
        """测试数据库连接"""
        db_engine = db_config.get('db_engine', '').lower()

        try:
            # 处理端口号，确保不为None且有默认值
            port = db_config.get('port')
            if port is None or port == '':
                # 根据数据库类型设置默认端口
                if db_engine == 'postgresql':
                    port = 5432
                elif db_engine == 'mysql':
                    port = 3306
                else:
                    port = None
            else:
                # 确保端口号是整数
                port = int(port)

            if db_engine == 'postgresql':
                conn = psycopg2.connect(
                    host=db_config.get('host'),
                    port=port,
                    user=db_config.get('user'),
                    password=db_config.get('password'),
                    database=db_config.get('database')
                )
            elif db_engine == 'mysql':
                conn = mysql_connect(
                    host=db_config.get('host'),
                    port=port,
                    user=db_config.get('user'),
                    password=db_config.get('password'),
                    database=db_config.get('database')
                )
            elif db_engine == 'sqlite':
                db_path = db_config.get('database', '')
                if not db_path:
                    return False, "SQLite数据库路径不能为空"
                # 对于SQLite，确保路径存在
                db_dir = os.path.dirname(db_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                conn = sqlite_connect(db_path)
            else:
                return False, "不支持的数据库类型"

            conn.close()
            return True, "数据库连接成功"
        except ValueError as ve:
            return False, f"参数错误: {str(ve)}"
        except Exception as e:
            return False, f"数据库连接失败: {str(e)}"

    @staticmethod
    def generate_env_file(config_data):
        """生成 .env 配置文件"""
        env_content = f"""# 数据库配置
DB_ENGINE={config_data.get('db_engine', 'postgresql')}
DB_HOST={config_data.get('db_host')}
DB_PORT={config_data.get('db_port')}
DB_NAME={config_data.get('db_name')}
DB_USER={config_data.get('db_user')}
DB_PASSWORD={config_data.get('db_password')}
DB_POOL_SIZE={config_data.get('db_pool_size', 16)}

# 通用配置
DOMAIN={config_data.get('domain')}
TITLE={config_data.get('title')}
BEIAN={config_data.get('beian', '')}

# 安全配置
SECRET_KEY={config_data.get('secret_key')}
JWT_EXPIRATION_DELTA={config_data.get('jwt_expiration', 604800)}
REFRESH_TOKEN_EXPIRATION_DELTA={config_data.get('refresh_expiration', 604800)}

# 邮件配置
MAIL_HOST={config_data.get('mail_host', '')}
MAIL_PORT={config_data.get('mail_port', 465)}
MAIL_USER={config_data.get('mail_user', '')}
MAIL_PASSWORD={config_data.get('mail_password', '')}

# Redis配置
REDIS_HOST={config_data.get('redis_host', 'localhost')}
REDIS_PORT={config_data.get('redis_port', 6379)}
REDIS_PASSWORD={config_data.get('redis_password', '')}
REDIS_DB={config_data.get('redis_db', 0)}
"""
        return env_content


guide_config = GuideConfig()


@guide_bp.route('/guide')
@skip_auth
def guide_index():
    """引导首页"""
    try:
        return render_template('guide/guide.html', steps=guide_config.steps, current_step=0)
    except Exception as e:
        return jsonify({'success': False, 'message': f'加载引导页面失败: {str(e)}'})


@guide_bp.route('/guide/test-db', methods=['POST'])
@skip_auth
def test_database():
    """测试数据库连接"""
    data = request.get_json()
    print("测试数据库连接数据:", data)

    # 统一的字段名映射处理
    def get_field(*possible_names):
        for name in possible_names:
            value = data.get(name)
            if value is not None and value != '':
                return value
        return None

    db_config = {
        'db_engine': get_field('db_engine', 'engine'),
        'host': get_field('db_host', 'host'),
        'port': get_field('db_port', 'port'),
        'user': get_field('db_user', 'user'),
        'password': get_field('db_password', 'password'),
        'database': get_field('db_name', 'database', 'db_database')
    }

    print("处理后的数据库配置:", db_config)

    # 验证必需字段
    if not db_config['db_engine']:
        return jsonify({'success': False, 'message': '请选择数据库类型'})

    if db_config['db_engine'] != 'sqlite':
        required_fields = ['host', 'user', 'database']
        missing_fields = [field for field in required_fields if not db_config[field]]
        if missing_fields:
            return jsonify({'success': False, 'message': f'缺少必需字段: {", ".join(missing_fields)}'})

    success, message = guide_config.test_database_connection(db_config)
    return jsonify({'success': success, 'message': message})


@guide_bp.route('/guide/generate-secret', methods=['POST'])
@skip_auth
def generate_secret():
    """生成 SECRET_KEY"""
    secret_key = guide_config.generate_secret_key()
    return jsonify({'secret_key': secret_key})


@guide_bp.route('/guide/save-config', methods=['POST'])
@skip_auth
def save_config():
    """保存配置文件"""
    try:
        data = request.get_json()
        print("保存配置数据:", data)

        # 生成环境文件内容
        env_content = guide_config.generate_env_file(data)

        # 确定 .env 文件路径
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(base_dir, '.env')

        # 备份现有配置文件（如果存在）
        if os.path.exists(env_path):
            backup_path = env_path + '.backup'
            os.rename(env_path, backup_path)

        # 写入新的配置文件
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)

        print(f"配置文件已保存到: {env_path}")

        # 如果是最后一步，创建管理员账户
        if data.get('step') == 'complete':
            admin_data = data.get('admin', {})
            # 这里可以添加创建管理员账户的逻辑
            # 需要等待系统重启后执行数据库初始化

        return jsonify({
            'success': True,
            'message': '配置保存成功',
            'env_path': env_path
        })

    except Exception as e:
        print(f"保存配置失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'保存配置失败: {str(e)}'
        })


@guide_bp.route('/guide/restart-info')
@skip_auth
def restart_info():
    """获取重启信息"""
    return jsonify({
        'manual_restart': True,  # 使用手动重启方案
        'commands': [
            '手动重启命令:',
            '1. 如果使用开发服务器: Ctrl+C 然后重新启动',
            '2. 如果使用生产服务器: 重启对应的服务进程',
            '3. 如果使用 Docker: docker restart <container_name>',
            '4. 如果使用 systemd: systemctl restart your-service'
        ]
    })
