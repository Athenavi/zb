import configparser
import os

import mysql.connector
from mysql.connector import pooling


def get_db_connection():
    global db_pool  # 确保可以在函数内使用全局变量db_pool

    # 如果连接池尚未初始化，则初始化之
    if db_pool is None:
        print('initializing database pool...')
        db_host = os.environ.get('db_host', '').strip("'")
        db_port = int(os.environ.get('db_port', '3306').strip("'"))
        db_name = os.environ.get('db_name', '').strip("'")
        db_user = os.environ.get('db_user', '').strip("'")
        db_password = os.environ.get('db_password', '').strip("'")

        if not all([db_host, db_port, db_name, db_user, db_password]):
            config = configparser.ConfigParser()
            try:
                config.read('config.ini', encoding='utf-8')
            except UnicodeDecodeError:
                config.read('config.ini', encoding='gbk')

            db_config = dict(config.items('database'))

            db_host = db_config.get('host', '').strip("'")
            db_port = int(db_config.get('port', '').strip("'"))
            db_name = db_config.get('database', '').strip("'")
            db_user = db_config.get('user', '').strip("'")
            db_password = db_config.get('password', '').strip("'")

        db_pool = pooling.MySQLConnectionPool(
            pool_name="zb_pool",
            pool_size=16,
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name,
            pool_reset_session=True
        )

    # 从连接池获取连接
    return db_pool.get_connection()


def test_database_connection():
    try:
        test_db = get_db_connection()
        test_db.close()
        print("Database connection is successful.")
    except mysql.connector.Error as err:
        print(f"Failed to connect to the database: {err}")


def check_db():
    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            # 执行查询
            sql = "SHOW TABLES"  # 查询所有表的SQL语句
            cursor.execute(sql)
            result = cursor.fetchall()

            # 检查查询结果
            if result:
                table_names = [row[0] for row in result]
                if len(table_names) <= 6:
                    print("/".join(table_names))
                else:
                    print("/".join(table_names[:3] + ["..."] + table_names[-3:]))
                print(f"Total tables: {len(result)}")
                print(f"----------------数据库表 预检测---------success")
                return len(result)
            else:
                print("No tables found in the database.")
                print(f"----------------数据库表丢失")
                return 0

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return None

    finally:
        # 关闭数据库连接
        if db:
            db.close()


db_pool = None
