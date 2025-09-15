# wsgi.py
import os
import sys
import argparse
from src.logger_config import init_optimized_logger


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='启动应用程序服务器')
    parser.add_argument('--port', type=int, default=9421,
                        help='应用程序运行的端口号 (默认: 9421)')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='绑定主机地址 (默认: 0.0.0.0)')
    parser.add_argument('--update', action='store_true',
                        help='启动前执行更新检查')
    parser.add_argument('--update-only', action='store_true',
                        help='仅执行更新而不启动服务器')
    return parser.parse_args()


def run_update():
    """执行更新程序"""
    print("正在检查更新...")
    try:
        # 导入并运行更新程序
        from update import main as update_main
        update_main()
        print("更新完成")
        return True
    except Exception as e:
        print(f"更新过程中出错: {str(e)}")
        return False


def main():
    # 解析命令行参数
    args = parse_arguments()

    # 初始化日志系统
    init_optimized_logger()

    # 检查配置文件
    if not os.path.isfile(".env"):
        print('配置文件不存在！详情请阅读 README.md')
        return

    # 处理更新选项
    if args.update_only:
        run_update()
        return

    if args.update:
        if not run_update():
            print("更新失败，继续使用当前版本启动")

    # 测试数据库连接
    from src.database import test_database_connection, check_db
    test_database_connection()
    check_db()

    # 导入应用
    from src.app import app

    # 显示端口信息
    print("=" * 50)
    print(f"应用程序正在启动...")
    print(f"服务地址: http://{args.host}:{args.port}")
    print(f"内部地址: http://127.0.0.1:{args.port}")
    print("=" * 50)
    print("您可以使用以下方式访问应用:")
    print(f"1. 直接访问: http://您的域名:{args.port}")
    print(f"2. 使用子域名: 将子域名解析到服务器IP，并通过反向代理将流量转发到端口 {args.port}")
    print("=" * 50)

    # 启动服务
    try:
        from waitress import serve
        serve(app, host=args.host, port=args.port, threads=8, channel_timeout=60)
    except KeyboardInterrupt:
        print("\n服务器正在关闭...")
    except Exception as e:
        print(f"服务器启动失败: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()