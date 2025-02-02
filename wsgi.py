from src.database import test_database_connection, check_db
import os
from waitress import serve


def main():
    if not os.path.isfile("config.ini"):
        print('配置文件不存在！详情请阅读 README.md')
        return
    if not os.path.exists('./temp/app.log'):
        print('日志文件未创建！')
        log_path = "temp"
        os.makedirs(log_path)
        file = open(log_path + "/app.log", "w", encoding='utf-8')
        file.write("------zyBlog------")
        file.close()
        print('success------日志文件已自动创建！！(提示:若创建失败，你可以自行创建 temp 目录并在其中创建 app.log 文件)')
        print('现在你可以重新启动程序！')
        return
    else:
        from src.app import app, domain, zb_safe_check
        if not zb_safe_check(domain):
            print('请修改默认安全密钥！config.ini[admin] 项')
            return
        import threading
        from src.notification import run_socketio
        test_database_connection()
        check_db()
        print("从浏览器打开: http://127.0.0.1:9421")

        # 启动 SocketIO 服务的线程
        socketio_thread = threading.Thread(target=run_socketio)
        socketio_thread.start()

        # 运行 Waitress
        serve(app, host='0.0.0.0', port=9421)


if __name__ == '__main__':
    main()
