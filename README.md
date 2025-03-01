<div align="center">
	<img src="https://7trees.cn/static/favicon.ico" width="160"  alt=""/>
	<h1>zyblog</h1>
</div>



> [!NOTE]
> 如果您觉得 `zyblog`对您有所帮助，或者您喜欢我们的项目，请在 GitHub 上给我们一个 ⭐️。您的支持是我们持续改进和增加新功能的动力！感谢您的支持！

- **更新日志**
    - [更新详情](./articles/changelog.md)
    - [旧版](https://github.com/Athenavi/zyBLOG)

## 预览

- [地址](https://7trees.cn)

[zyBLOG](https://github.com/Athenavi/zyBLOG) 是一个基于 Python Flask 和 WSGI 的简易博客程序

## 技术组成

- **Python Flask**: 作为 Web 框架，提供了构建网页应用的基础功能。
- **WSGI**: 作为 Python Web 应用程序与 Web 服务器之间的接口标准，实现了 Web 应用程序与服务器之间的通信。
- **HTML/CSS**: 用于构建博客界面的前端技术。
- **MySQL**: 作为数据库，用于存储用户、文章信息、评论等数据。

## 功能特点

- [x] 提供文章分类和标签功能，方便用户组织和浏览文章。
- [x] 界面适应手机
- [x] ~~SEO优化~~(自完全使用前端渲染之后,SEO功能可谓是完全丧失了)
- [x] 支持创建、编辑和删除博客文章。
- [x] 提供评论功能，让用户可以与其他用户进行交流和互动。
- [x] 用户可以注册和登录，以便管理他们的博客文章。
- [x] 博客文章可以包含图片、视频和代码片段。
- [x] 支持搜索功能，使用户可以快速找到感兴趣的文章。

## 示例图片

![](https://7trees.cn/zyImg/test/ac2764bba0b08d79e8f4bb1ba0d57a59.png)

## 如何运行

建议使用 **Linux宝塔面板**

1. 宝塔 **V9.0.0** 稳定版安装脚本

```sh
url=https://download.bt.cn/install/install_lts.sh;if [ -f /usr/bin/curl ];then curl -sSO $url;else wget -O install_lts.sh $url;fi;bash install_lts.sh ed8484bec
```

1. 克隆或下载 zyBLOG 代码库到本地。创建一个数据库，导入本项目里的 *sql* 文件（注意sql版本），复制 *config_example.ini* 文件到
   *config.ini* ，配置 *config.ini*
2. BT面板部署成功后(BT主程序页面 可以在 右侧 *网站* 选项卡配置Python项目,建议使用 Python V3.12.3 项目依赖
   requirements.txt)
3. 
通用python项目部署参考步骤 [https://www.bt.cn/bbs/thread-125161-1-1.html](https://www.bt.cn/bbs/thread-125161-1-1.html)

不使用宝塔?

1. 确保你的系统已经安装了 Python(建议3.12及以上版本) 和 pip。
2. 克隆或下载 zyBLOG 代码库到本地。创建一个数据库，导入本项目里的 *sql* 文件（注意sql版本），复制 *config_example.ini* 文件到
   *config.ini* ，配置 *config.ini*
3. 在终端中进入项目根目录，并执行以下命令的顺序执行以启动 zyBLOG 博客程序：

```bash
$ pip install -r requirements.txt
$ python wsgi.py
```
(可选)使用gunicorn运行一个高性能守护进程(--daemon)实例
```bash
$ touch ./temp/access.log && touch ./temp/error.log
$ sudo chmod 777 ./temp/access.log && sudo chmod 777 ./temp/error.log
$ gunicorn --workers 4 --threads 2 --bind 0.0.0.0:9421 --timeout 60 --access-logfile ./temp/access.log --error-logfile ./temp/error.log --daemon src.app:app
```
1. 在浏览器中访问 `http://localhost:9421`，即可进入 zyBLOG。
2. 管理后台 (/dashboard) 默认账号 'test' 默认密码 '123456'

## 无法运行？
   建议使用python虚拟环境
## python版本遇到问题？

- [更多问题](./articles/Linux上python多版本问题.md)
     
## 仍然无法运行？

如果你了解docker，可以尝试使用Dockerfile来部署运行


## 开源贡献者

感谢以下各位的贡献

<img src="https://contrib.rocks/image?repo=Athenavi/zb"  alt=""/>

## 交流

我们热烈欢迎并感谢所有形式的贡献。如果您有任何想法或建议，欢迎通过提交 [pull requests](https://github.com/soybeanjs/soybean-admin/pulls)
或创建 GitHub [issue](https://github.com/soybeanjs/soybean-admin/issues/new) 来分享。

## Star 趋势

![Star History Chart](https://api.star-history.com/svg?repos=Athenavi/zb&type=Date)

## 开源协议

项目基于 [Apache V2.0](./LICENSE) 协议，仅供学习参考，商业使用请保留作者版权信息，作者不保证也不承担任何软件的使用风险。

## 免责声明

zyBLOG 是一个个人项目，并未经过详尽测试和完善，因此不对其能力和稳定性做出任何保证。使用 zyBLOG 时请注意自己的数据安全和程序稳定性。任何由于使用
zyBLOG 造成的数据丢失、损坏或其他问题，作者概不负责。

**请谨慎使用 zyBLOG，并在使用之前备份你的数据。**

# 开发文档

## 概述

欢迎使用，在开始开发 zyBLOG 之前，你应该对 html、JavaScript、Python、MySql 数据库、服务器等有基本的认识。本文档是建立在这些基础知识之上的。

## 模板开发

在开发模板之前，先做好zyBLOG的环境搭建

### 模板的组成

一个完整的模板，文件内容如下：

```
newtemplate
├── index.html
├── screenshot.png
└── template.ini
```

其中 `index.html` 、 `screenshot.png` 、`template.ini` 是模板的必须文件，一个模板最少由这三个文件组成。

`index.html` : 网站首页的模板
`screenshot.png` : 后台的模板缩略图
`template.ini` 模板的配置信息

提示
当我们开始开发一个新的模板的时候，可以先用这三个文件，打包成 zip 包之后，通过 zyBLOG 后台进行上传安装。

或者可以把 NewTemplate 文件夹直接复制到 zyBLOG 的 templates/theme 目录下也等同于安装。

模板的配置文件 template.ini 内容如下

``` ini
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

`当至少我们拥有这三个文件之后 刷新我们的程序 那么新的模板 就会出现在后台模板中`