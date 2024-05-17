from waitress import serve
import os


def main():
    if not os.path.isfile("config.ini"):
        print('配置文件不存在！详情请阅读 README.md')
    if not os.path.exists('./temp/app.log'):
        print('日志文件未创建！')
        log_path = "temp"
        os.makedirs(log_path)
        file = open(log_path + "/app.log", "w", encoding='utf-8')
        file.write("------zyBlog------")
        file.close()
        print('success------日志文件已自动创建！！(提示:若创建失败，你可以自行创建 temp 目录并在其中创建 app.log 文件)')
        print('现在你可以重新启动程序！')

    else:
        from src.app import app
        from src.database import test_database_connection, CheckDatabase
        test_database_connection()
        CheckDatabase()
        print("从浏览器打开: http://127.0.0.1:5000")
        serve(app, host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()
