import logging
import os

import psycopg2
from dotenv import load_dotenv
from psycopg2 import pool

# 声明全局变量
db_pool = None

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db_pool():
    """初始化数据库连接池"""
    global db_pool
    if db_pool is not None:
        return db_pool

    # 加载 .env 文件
    load_dotenv()

    # 获取数据库配置
    db_config = {
        'host': os.environ.get('DB_HOST') or os.getenv('DATABASE_HOST'),
        'port': os.environ.get('DB_PORT') or os.getenv('DATABASE_PORT', '5432'),
        'dbname': os.environ.get('DB_NAME') or os.getenv('DATABASE_NAME'),
        'user': os.environ.get('DB_USER') or os.getenv('DATABASE_USER'),
        'password': os.environ.get('DB_PASSWORD') or os.getenv('DATABASE_PASSWORD')
    }

    # 检查配置是否完整
    if not all(db_config.values()):
        missing = [k for k, v in db_config.items() if not v]
        logger.error(f"数据库配置不完整，缺少: {missing}")
        raise ValueError("数据库连接配置不完整")

    # 获取连接池大小
    pool_size = int(os.environ.get('DB_POOL_SIZE', 16))

    try:
        logger.info('正在初始化PostgreSQL数据库连接池...')
        db_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=pool_size,
            **db_config
        )
        logger.info(f"PostgreSQL连接池初始化成功，池大小: {pool_size}")
        return db_pool
    except psycopg2.Error as e:
        logger.error(f"连接池初始化失败: {e}")
        raise


def get_db_connection():
    """从连接池获取数据库连接"""
    global db_pool

    try:
        # 如果连接池未初始化，先初始化
        if db_pool is None:
            init_db_pool()

        # 从连接池获取连接
        connection = db_pool.getconn()
        if connection is None:
            logger.error("从连接池获取连接失败，得到None")
            raise Exception("无法从连接池获取数据库连接")

        logger.debug("成功获取数据库连接")
        return connection

    except Exception as e:
        logger.error(f"获取数据库连接失败: {e}")
        # 尝试重新初始化连接池
        try:
            db_pool = None
            init_db_pool()
            connection = db_pool.getconn()
            return connection
        except:
            raise


def release_db_connection(connection):
    """释放连接回连接池"""
    global db_pool

    try:
        if db_pool is not None and connection is not None:
            # 检查连接是否仍然有效
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
            except:
                # 连接已失效，关闭它
                connection.close()
                return

            # 连接有效，放回连接池
            db_pool.putconn(connection)
            logger.debug("成功释放数据库连接回连接池")
    except Exception as e:
        logger.error(f"释放数据库连接失败: {e}")
        # 如果归还连接失败，尝试关闭连接
        try:
            if connection and not connection.closed:
                connection.close()
        except:
            pass


def get_sqlalchemy_uri():
    """获取SQLAlchemy数据库URI"""
    # 加载 .env 文件
    load_dotenv()

    db_host = os.environ.get('DB_HOST') or os.getenv('DATABASE_HOST')
    db_port = os.environ.get('DB_PORT') or os.getenv('DATABASE_PORT', '5432')
    db_name = os.environ.get('DB_NAME') or os.getenv('DATABASE_NAME')
    db_user = os.environ.get('DB_USER') or os.getenv('DATABASE_USER')
    db_password = os.environ.get('DB_PASSWORD') or os.getenv('DATABASE_PASSWORD')

    if not all([db_host, db_port, db_name, db_user, db_password]):
        logger.error('数据库连接配置不完整，请检查 .env 文件或环境变量。')
        return None

    # 构建SQLAlchemy数据库URI
    sqlalchemy_uri = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    logger.info(f"SQLAlchemy URI: {sqlalchemy_uri.replace(db_password, '***')}")  # 安全日志
    return sqlalchemy_uri


def test_database_connection():
    """测试数据库连接"""
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("无法获取数据库连接。")
            return False

        # 执行简单查询测试连接
        with conn.cursor() as cursor:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()
            logger.info(f"PostgreSQL版本: {version[0]}")

        logger.info("数据库连接测试成功。")
        return True

    except psycopg2.Error as err:
        logger.error(f"连接数据库失败: {err}")
        return False
    finally:
        if conn:
            release_db_connection(conn)


def check_db():
    """检查数据库表结构"""
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("无法获取数据库连接。")
            return None

        with conn.cursor() as cursor:
            # PostgreSQL 查询所有表的SQL语句
            sql = """
                  SELECT table_name
                  FROM information_schema.tables
                  WHERE table_schema = 'public'
                  ORDER BY table_name
                  """
            cursor.execute(sql)
            result = cursor.fetchall()

            # 检查查询结果
            if result:
                table_names = [row[0] for row in result]
                if len(table_names) <= 6:
                    tables_str = "/".join(table_names)
                else:
                    tables_str = "/".join(table_names[:3] + ["..."] + table_names[-3:])

                logger.info(f"检测到表: {tables_str}")
                logger.info(f"总表数: {len(result)}")
                print(f"----------------数据库表预检测成功---------")
                return len(result)
            else:
                logger.warning("数据库中没有找到表。")
                print(f"----------------数据库表丢失")
                return 0

    except psycopg2.Error as err:
        logger.error(f"数据库错误: {err}")
        return None
    finally:
        if conn:
            release_db_connection(conn)


def check_pool_health():
    """检查连接池健康状态"""
    global db_pool
    if db_pool is None:
        return "连接池未初始化"

    conn = None
    try:
        # 尝试获取和释放一个连接来测试池的健康状况
        conn = db_pool.getconn()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result and result[0] == 1:
                return "连接池健康"
            else:
                return "连接池响应异常"
    except Exception as e:
        return f"连接池不健康: {e}"
    finally:
        if conn:
            db_pool.putconn(conn)


def close_all_connections():
    """关闭所有数据库连接"""
    global db_pool
    if db_pool is not None:
        try:
            db_pool.closeall()
            logger.info("已关闭所有数据库连接")
        except Exception as e:
            logger.error(f"关闭连接池失败: {e}")
        finally:
            db_pool = None


# 使用上下文管理器更安全地处理连接
class DBConnection:
    """数据库连接上下文管理器"""

    def __enter__(self):
        self.conn = get_db_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            release_db_connection(self.conn)


# 使用示例函数
def example_usage():
    """使用示例"""
    # 方法1: 使用上下文管理器（推荐）
    try:
        with DBConnection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM users")
                count = cursor.fetchone()
                print(f"用户数量: {count[0]}")
    except Exception as e:
        logger.error(f"查询失败: {e}")

    # 方法2: 手动管理连接
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT table_name FROM information_schema.tables LIMIT 5")
            tables = cursor.fetchall()
            print("前5个表:", [table[0] for table in tables])
    except Exception as e:
        logger.error(f"查询失败: {e}")
    finally:
        if conn:
            release_db_connection(conn)


if __name__ == "__main__":
    # 测试代码
    print("开始测试数据库连接...")
    if test_database_connection():
        print("✓ 数据库连接测试成功")
        table_count = check_db()
        print(f"✓ 数据库表检查完成，找到 {table_count} 张表")

        # 检查连接池健康状态
        health = check_pool_health()
        print(f"✓ 连接池健康状态: {health}")
    else:
        print("✗ 数据库连接测试失败")

    # 清理资源
    close_all_connections()
