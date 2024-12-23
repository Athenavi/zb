import configparser
import os

import mysql.connector


def get_db_connection():
    return get_database_connection()


def get_database_connection():
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

    zy_db = mysql.connector.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name
    )
    return zy_db


def test_database_connection():
    try:
        test_db = get_database_connection()
        test_db.close()
        print("Database connection is successful.")
    except mysql.connector.Error as err:
        print(f"Failed to connect to the database: {err}")


def check_db():
    global cursor, db
    try:
        db = get_database_connection()
        cursor = db.cursor()

        # 执行查询
        sql = "SHOW TABLES"  # 查询所有表的SQL语句
        cursor.execute(sql)
        result = cursor.fetchall()

        # 检查查询结果
        if result:
            for row in result:
                print(row[0], end="/")
            print(f"Total tables: {len(result)}")
            print(f"----------------数据库表 预检测---------success")
        else:
            print("No tables found in the database.")
            print(f"----------------数据库表丢失")
            return 0

    finally:
        # 关闭数据库连接
        cursor.close()
        db.close()

    return len(result)
