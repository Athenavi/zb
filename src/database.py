import logging
import os
from contextlib import contextmanager

import psycopg2
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


engine = create_engine(
    get_sqlalchemy_uri()
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db():
    """
    提供数据库session的上下文管理器，确保session正确关闭
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"数据库操作失败: {e}")
        raise
    finally:
        db.close()


def test_database_connection():
    """测试数据库连接"""
    with get_db() as session:
        try:
            result = session.execute(text("SELECT version()")).scalar()
            logger.info(f"PostgreSQL版本: {result}")
            logger.info("数据库连接测试成功。")
            return True
        except psycopg2.Error as err:
            logger.error(f"连接数据库失败: {err}")
            return False
        except Exception as e:
            logger.error(f"测试数据库连接时发生错误: {e}")
            return False


def check_db():
    """检查数据库表结构"""
    with get_db() as session:
        # 使用 ORM 检查所有表的结构
        inspector = inspect(engine)
        table_names = inspector.get_table_names(schema='public')

        # 检查查询结果
        if table_names:
            if len(table_names) <= 6:
                tables_str = "/".join(table_names)
            else:
                tables_str = "/".join(table_names[:3] + ["..."] + table_names[-3:])

            logger.info(f"检测到表: {tables_str}")
            logger.info(f"总表数: {len(table_names)}")
            print(f"----------------数据库表预检测成功---------")
            return len(table_names)
        else:
            logger.warning("数据库中没有找到表。")
            print(f"----------------数据库表丢失")
            return 0


if __name__ == "__main__":
    # 测试代码
    print("开始测试数据库连接...")
    if test_database_connection():
        print("✓ 数据库连接测试成功")
        table_count = check_db()
        print(f"✓ 数据库表检查完成，找到 {table_count} 张表")
    else:
        print("✗ 数据库连接测试失败")
