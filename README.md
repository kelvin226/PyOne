# PyOne - 基于Python的onedrive文件本地化浏览系统,使用MongoDB缓存文件


## 适用onedrive版本 ##
1. 个人版
2. onedrive商业版
3. onedrive教育版（需要学校管理员开启权限）

## 特性 ##
1. 简单易用。只需简单设置，即可做一个onedrive文件列表分享程序
2. 功能丰富。
    - 可设置文件夹密码。只需在文件夹添加`.password`文件，内容为密码内容，即可在该文件夹设置密码
    - 可设置README。
3. 后台强大。
    - **防盗链设置**。
    - **后台上传文件**。
    - **后台更新文件**。
    - **后台设置统计代码**
    - **后台管理onedrive文件**。
        - **删除onedrive文件**
        - **直接在后台给文件夹添加`.password`和`README`和`HEAD`**
        - **直接在后台编辑文本文件**。
        - **上传本地文件至onedrive**

## 适用环境 ##
1. linux环境（推荐centos7）
2. Python2.7
3. **需要安装redis，MongoDB**

**推荐预先安装宝塔，再进行安装**

## 安装教程 ##
请转移到我的博客查看[安装教程](https://abbeyok.com/2018/09/23/pyone2-0/)

## 更新源码步骤 ##
1. 先将data目录和config.py复制出去
2. 删除原来的PyOne源码
3. 重新git clone一份PyOne源码
4. 将原来的data目录替换新源码的data目录，原来的config.py替换新源码的config.py
5. 重新安装依赖，看是否有新增的依赖包：
```
pip install -r requirements.txt
```
6. 重启网站：
```
supervisorctl -c supervisord.conf restart pyone
```
7. 最好更新一下文件缓存：
```
python function.py UpdateFile
```

## 提供安装服务 ##
[点击购买](https://iofaka.com/?gid=4)
