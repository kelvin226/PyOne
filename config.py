#-*- coding=utf-8 -*-
import os

#限制调用域名
allow_site=[u'no-referrer']

#######源码目录
config_dir='/root/PyOne'
data_dir=os.path.join(config_dir,'data')

#######分享目录
share_path="/"

#onedrive api设置
redirect_uri='https://auth.3pp.me/' #不要修改！
BaseAuthUrl='https://login.microsoftonline.com'
client_id=""
client_secret=""


#下载链接过期时间
downloadUrl_timeout="300"

#onedrive个人页的域名。国际版为com结尾，世纪互联版为cn结尾，最后面一定要带/
app_url=u'https://graph.microsoft.com/'

#后台密码设置
password="PyOne"

#网站名称
title="PyOne"

tj_code=''
