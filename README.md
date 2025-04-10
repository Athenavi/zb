此项目为旧版本 zyBLOG，现已迁移至新版本 [zyBlog-2.0](https://github.com/Athenavi/zb-v2)
<div align="center">
  <h1>zyBLOG - 轻量易用的Python Flask博客系统</h1>
  
  [![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
  [![Flask Version](https://img.shields.io/badge/flask-3.1.x-green.svg)](https://flask.palletsprojects.com/)
  [![License](https://img.shields.io/badge/license-Apache%202.0-orange.svg)](./LICENSE)
  [![GitHub Stars](https://img.shields.io/github/stars/Athenavi/zb.svg?style=social)](https://github.com/Athenavi/zb/stargazers)

</div>

## 🌟 项目亮点

- **Python实现** - 基于Flask框架
- **响应式设计** - 完美适配桌面与移动设备
- **轻量高效** - 核心功能精简

## 🚀 快速开始

### 环境要求
- Python 3.12+
- MySQL 5.7+

### 宝塔面板部署（新手推荐）
```bash
# 安装宝塔面板（国内服务器）
url=https://download.bt.cn/install/install_lts.sh && \
curl -sSO $url || wget -O install_lts.sh $url && \
bash install_lts.sh ed8484bec

# 安装后通过Web界面配置：
1. 创建Python项目（推荐3.12.x）
2. 导入项目仓库
3. 配置MySQL数据库
4. 安装依赖：pip install -r requirements.txt
```

### 手动部署
```bash
# 克隆仓库
git clone https://github.com/Athenavi/zb.git
cd zb

# 初始化环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置数据库
cp config_example.ini config.ini
# 编辑config.ini中的数据库配置

# 启动服务
python wsgi.py
```

```bash
$ pip install -r requirements.txt
$ python wsgi.py
```

(可选) 使用gunicorn运行高性能守护进程实例：
```bash
$ touch ./temp/access.log && touch ./temp/error.log
$ sudo chmod 777 ./temp/access.log && sudo chmod 777 ./temp/error.log
$ gunicorn --workers 4 --threads 2 --bind 0.0.0.0:9421 --timeout 60 --access-logfile ./temp/access.log --error-logfile ./temp/error.log --daemon src.app:app
```
1. 在浏览器中访问 `http://localhost:9421`，即可进入 zyBLOG。
2. 管理后台 (/dashboard) 默认账号 'test'，默认密码 '123456'。

## 遇到Python版本问题？

- [更多问题](./articles/Linux上python多版本问题.md)

## 仍然无法运行？

如果您熟悉Docker，可以尝试使用Dockerfile进行部署。

## 📚 功能概览

| 模块         | 功能               | 状态 |
|--------------|------------------|------|
| 文章管理     | Markdown支持/标签/搜索 | ✅   |
| 用户系统     | 注册/登录/自定义        | ✅   |
| 评论系统     | 嵌套评论/审核机制        | ✅   |
| 后台管理     | 用户管理/内容管理        | ✅   |
| SEO优化      | 自动生成sitemap/规范链接 | ✅   |
| 主题系统     | 多主题支持/热切换        | 🚧   |
| API接口      | RESTful API设计    | 🚧   |

## 📸 移动端界面预览

![新版首页界面](https://7trees.cn/media/test/preview.png)
*▲ 响应式后台管理界面*

## 🛠️ 开发者指南

### 项目结构
```bash
├── src/                 # 核心源代码
├── templates/           # 前端模板
├── static/              # 静态资源
├── requirements.txt     # 依赖清单
└── wsgi.py              # 启动入口
```

### 模板开发

在开发模板之前，确保完成zyBLOG的环境搭建。

#### 模板的组成

一个完整的模板应包含以下文件：

```
newtemplate
├── index.html
├── screenshot.png
└── template.ini
```

- `index.html` : 网站首页的模板
- `screenshot.png` : 后台的模板缩略图
- `template.ini` : 模板的配置信息

**提示**：您可以将这三个文件打包成zip文件，通过zyBLOG后台进行上传安装，或者直接将NewTemplate文件夹复制到zyBLOG的templates/theme目录下。

模板的配置文件`template.ini`内容如下：

```ini
[default]
id = 'cn.7trees.2024'
title = '2024Theme'
description = '2024Theme_for_zyBLOG'
author = '7trees'
authorWebsite = 'https://7trees.cn'
version = '1.0'
versionCode = '1'
updateUrl = ''
screenshot = 'screenshot.png'
```

确保拥有这三个文件后，刷新程序，新的模板将出现在后台模板中。

## 📈 用户增长

![Star History Chart](https://api.star-history.com/svg?repos=Athenavi/zb&type=Date)

## 🤝 开源协议

本项目采用 [Apache License 2.0](./LICENSE) 开源协议，您可以在遵守协议条款的前提下自由使用、修改和分发代码。

## 📬 联系我们

- 示例网站：[7trees.cn](https://7trees.cn)
- 问题反馈：[GitHub Issues](https://github.com/Athenavi/zb/issues)
- 社区讨论：QQ群（暂未开放）

---

> 💡 提示：项目持续迭代中，建议使用 `main` 分支获取最新更新。

