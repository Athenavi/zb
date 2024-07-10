# 使用基础镜像
FROM python:3.12.4

# 设置工作目录
WORKDIR /app

# 将应用程序代码复制到容器中
COPY . /app

# 安装依赖
RUN pip install -r requirements.txt

# 暴露端口 5000
EXPOSE 5000

ENV db_host=''
ENV db_port=''
ENV db_name=''
ENV db_user=''
ENV db_password=''

# 定义启动命令
CMD ["python", "wsgi.py"]
