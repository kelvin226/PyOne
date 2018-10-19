#-*- coding=utf-8 -*-
from flask import Flask,render_template,redirect,abort,make_response,jsonify,request,url_for,Response
from flask_sqlalchemy import Pagination
import json
from collections import OrderedDict
import subprocess
import hashlib
import random
import markdown
from function import *
from config import *
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from shelljob import proc
import time
import os
import sys
import eventlet

eventlet.monkey_patch()

reload(sys)
sys.setdefaultencoding("utf-8")


#######flask
app=Flask(__name__)
app.secret_key=os.path.join(config_dir,'PyOne'+password)
cache = Cache(app, config={'CACHE_TYPE': 'redis'})
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200/minute", "50/second"],
)


################################################################################
###################################功能函数#####################################
################################################################################
def md5(string):
    a=hashlib.md5()
    a.update(string.encode(encoding='utf-8'))
    return a.hexdigest()

def GetTotal(path):
    key='total:{}'.format(path)
    if rd.exists(key):
        return int(rd.get(key))
    else:
        if path=='/':
            total=items.find({'grandid':0}).count()
        else:
            f=items.find_one({'path':path})
            pid=f['id']
            total=items.find({'parent':pid}).count()
            rd.set(key,total,300)
        return total


# @cache.memoize(timeout=60*5)
def FetchData(path='/',page=1,per_page=50,sortby='lastModtime',order='desc',dismiss=False):
    path=urllib.unquote(path)
    resp=[]
    if sortby not in ['lastModtime','type','size','name']:
        sortby='lastModtime'
    if sortby=='size':
        sortby='size_order'
    if order=='desc':
        order=DESCENDING
    else:
        order=ASCENDING
    try:
        if path=='/':
            data=items.find({'grandid':0}).collation({"locale": "zh", 'numericOrdering':True})\
                .sort([('order',ASCENDING),(sortby,order)])\
                .limit(per_page).skip((page-1)*per_page)
            for d in data:
                item={}
                item['name']=d['name']
                item['id']=d['id']
                item['lastModtime']=d['lastModtime']
                item['size']=d['size']
                item['type']=d['type']
                if dismiss:
                    if d['name'] not in ('README.md','README.txt','readme.md','readme.txt','.password','HEAD.md','HEAD.txt','head.md','head.txt'):
                        resp.append(item)
                else:
                    resp.append(item)
            total=GetTotal(path)
        else:
            f=items.find_one({'path':path})
            pid=f['id']
            if f['type']!='folder':
                return f,'files'
            data=items.find({'parent':pid}).collation({"locale": "zh", 'numericOrdering':True})\
                .sort([('order',ASCENDING),(sortby,order)])\
                .limit(per_page).skip((page-1)*per_page)
            for d in data:
                item={}
                item['name']=d['name']
                item['id']=d['id']
                item['lastModtime']=d['lastModtime']
                item['size']=d['size']
                item['type']=d['type']
                if dismiss:
                    if d['name'] not in ('README.md','README.txt','readme.md','readme.txt','.password','HEAD.md','HEAD.txt','head.md','head.txt'):
                        resp.append(item)
                else:
                    resp.append(item)
            total=GetTotal(path)
    except:
        resp=[]
        total=0
    return resp,total

@cache.memoize(timeout=60*5)
def _thunbnail(id):
    app_url=GetAppUrl()
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token),'Content-type':'application/json'}
    url=app_url+'v1.0/me/drive/items/{}/thumbnails/0?select=large'.format(id)
    r=requests.get(url,headers=headers)
    data=json.loads(r.content)
    if data.get('large').get('url'):
        return data.get('large').get('url')
    else:
        return False

@cache.memoize(timeout=60*5)
def _getdownloadurl(id):
    app_url=GetAppUrl()
    token=GetToken()
    filename=GetName(id)
    ext=filename.split('.')[-1]
    if ext in ['webm','avi','mpg', 'mpeg', 'rm', 'rmvb', 'mov', 'wmv', 'mkv', 'asf']:
        downloadUrl=_thunbnail(id)
        downloadUrl=downloadUrl.replace('thumbnail','videomanifest')+'&part=index&format=dash&useScf=True&pretranscode=0&transcodeahead=0'
        return downloadUrl
    else:
        headers={'Authorization':'bearer {}'.format(token),'Content-type':'application/json'}
        url=app_url+'v1.0/me/drive/items/'+id
        r=requests.get(url,headers=headers)
        data=json.loads(r.content)
        if data.get('@microsoft.graph.downloadUrl'):
            return data.get('@microsoft.graph.downloadUrl')
        else:
            return False

def GetDownloadUrl(id):
    if rd.exists('downloadUrl2:{}'.format(id)):
        downloadUrl,ftime=rd.get('downloadUrl2:{}'.format(id)).split('####')
        if time.time()-int(ftime)>=600:
            # print('{} downloadUrl expired!'.format(id))
            downloadUrl=_getdownloadurl(id)
            ftime=int(time.time())
            k='####'.join([downloadUrl,str(ftime)])
            rd.set('downloadUrl2:{}'.format(id),k)
        else:
            # print('get {}\'s downloadUrl from cache'.format(id))
            downloadUrl=downloadUrl
    else:
        # print('first time get downloadUrl from {}'.format(id))
        downloadUrl=_getdownloadurl(id)
        ftime=int(time.time())
        k='####'.join([downloadUrl,str(ftime)])
        rd.set('downloadUrl2:{}'.format(id),k)
    return downloadUrl


def GetName(id):
    key='name:{}'.format(id)
    if rd.exists(key):
        return rd.get(key)
    else:
        item=items.find_one({'id':id})
        rd.set(key,item['name'])
        return item['name']

def GetPath(id):
    key='path:{}'.format(id)
    if rd.exists(key):
        return rd.get(key)
    else:
        item=items.find_one({'id':id})
        rd.set(key,item['path'])
        return item['path']

# @cache.memoize(timeout=60*5)
def GetReadMe(path):
    # README
    ext='Markdown'
    readme,_,i=has_item(path,'README.md')
    if readme==False:
        readme,_,i=has_item(path,'readme.md')
    if readme==False:
        ext='Text'
        readme,_,i=has_item(path,'readme.txt')
    if readme==False:
        ext='Text'
        readme,_,i=has_item(path,'README.txt')
    if readme!=False:
        readme=markdown.markdown(readme)
    return readme,ext


# @cache.memoize(timeout=60*5)
def GetHead(path):
    # README
    ext='Markdown'
    head,_,i=has_item(path,'HEAD.md')
    if head==False:
        head,_,i=has_item(path,'head.md')
    if head==False:
        ext='Text'
        head,_,i=has_item(path,'head.txt')
    if head==False:
        ext='Text'
        head,_,i=has_item(path,'HEAD.txt')
    if head!=False:
        head=markdown.markdown(head)
    return head,ext


def CanEdit(filename):
    ext=filename.split('.')[-1]
    if ext in ["html","htm","php","css","go","java","js","json","txt","sh","md",".password"]:
        return True
    else:
        return False

def CodeType(ext):
    code_type={}
    code_type['html'] = 'html';
    code_type['htm'] = 'html';
    code_type['php'] = 'php';
    code_type['css'] = 'css';
    code_type['go'] = 'golang';
    code_type['java'] = 'java';
    code_type['js'] = 'javascript';
    code_type['json'] = 'json';
    code_type['txt'] = 'Text';
    code_type['sh'] = 'sh';
    code_type['md'] = 'Markdown';
    return code_type.get(ext.lower())

def file_ico(item):
  ext = item['name'].split('.')[-1].lower()
  if ext in ['bmp','jpg','jpeg','png','gif']:
    return "image";

  if ext in ['mp4','mkv','webm','avi','mpg', 'mpeg', 'rm', 'rmvb', 'mov', 'wmv', 'mkv', 'asf']:
    return "ondemand_video";

  if ext in ['ogg','mp3','wav']:
    return "audiotrack";

  return "insert_drive_file";

def _remote_content(fileid):
    kc='{}:content'.format(fileid)
    if rd.exists(kc):
        return rd.get(kc)
    else:
        downloadUrl=GetDownloadUrl(fileid)
        if downloadUrl:
            r=requests.get(downloadUrl)
            r.encoding='utf-8'
            content=r.content
            rd.set(kc,content)
            return content
        else:
            return False

# @cache.memoize(timeout=60)
def has_item(path,name):
    if items.count()==0:
        return False
    key='has_item$#$#$#$#{}$#$#$#$#{}'.format(path,name)
    if rd.exists(key):
        values=rd.get(key)
        item,fid,cur=values.split('########')
        if item=='False':
            item=False
        if cur=='False':
            cur=False
        else:
            cur=True
        if fid=='False':
            fid=False
        return item,fid,cur
    else:
        item=False
        fid=False
        dz=False
        cur=False
        if name=='.password':
            dz=True
        try:
            if path=='/':
                if items.find_one({'grandid':0,'name':name}):
                    fid=items.find_one({'grandid':0,'name':name})['id']
                    item=_remote_content(fid).strip()
            else:
                route=path.split('/')
                if name=='.password':
                    for idx,r in enumerate(route):
                        p='/'.join(route[:idx+1])
                        f=items.find_one({'path':p})
                        pid=f['id']
                        data=items.find_one({'name':name,'parent':pid})
                        if data:
                            fid=data['id']
                            item=_remote_content(fid).strip()
                            if idx==len(route)-1:
                                cur=True
                else:
                    f=items.find_one({'path':path})
                    pid=f['id']
                    data=items.find_one({'name':name,'parent':pid})
                    if data:
                        fid=data['id']
                        item=_remote_content(fid).strip()
        except:
            item=False
        rd.set(key,'{}########{}########{}'.format(item,fid,cur))
        return item,fid,cur


def verify_pass_before(path):
    plist=path_list(path)
    for i in [i for i in range(len(plist))]:
        n='/'.join(plist[:-i])
        yield n

def has_verify(path):
    verify=False
    md5_p=md5(path)
    passwd,fid,cur=has_item(path,'.password')
    if fid and cur:
        vp=request.cookies.get(md5_p)
        if passwd==vp:
            verify=True
    else:
        for last in verify_pass_before(path):
            if last=='':
                last='/'
            passwd,fid,cur=has_item(last,'.password')
            md5_p=md5(last)
            vp=request.cookies.get(md5_p)
            if passwd==vp:
                verify=True
    return verify


def path_list(path):
    if path=='/':
        return [path]
    if path.startswith('/'):
        path=path[1:]
    if path.endswith('/'):
        path=path[:-1]
    plist=path.split('/')
    return plist


################################################################################
###################################试图函数#####################################
################################################################################
@app.before_request
def before_request():
    bad_ua=['Googlebot-Image','FeedDemon ','BOT/0.1 (BOT for JCE)','CrawlDaddy ','Java','Feedly','UniversalFeedParser','ApacheBench','Swiftbot','ZmEu','Indy Library','oBot','jaunty','YandexBot','AhrefsBot','MJ12bot','WinHttp','EasouSpider','HttpClient','Microsoft URL Control','YYSpider','jaunty','Python-urllib','lightDeckReports Bot','PHP','vxiaotou-spider','spider']
    global referrer
    try:
        ip = request.headers['X-Forwarded-For'].split(',')[0]
    except:
        ip = request.remote_addr
    try:
        ua = request.headers.get('User-Agent')
    except:
        ua="null"
    if sum([i.lower() in ua.lower() for i in bad_ua])>0:
        return redirect('http://www.baidu.com')
    # print '{}:{}:{}'.format(request.endpoint,ip,ua)
    referrer=request.referrer if request.referrer is not None else 'no-referrer'

@app.route('/<path:path>',methods=['POST','GET'])
@app.route('/',methods=['POST','GET'])
@limiter.limit("200/minute;50/second")
def index(path='/'):
    if path=='favicon.ico':
        return redirect('https://onedrive.live.com/favicon.ico')
    if items.count()==0:
        if not os.path.exists(os.path.join(config_dir,'data/token.json')):
            return redirect(url_for('admin.install',step=0))
        else:
            #subprocess.Popen('python {} UpdateFile'.format(os.path.join(config_dir,'function.py')),shell=True)
            return make_response('<h1>正在更新数据！如果您是网站管理员，请在后台运行命令：python function.py UpdateFile</h1>')
    #参数
    page=request.args.get('page',1,type=int)
    image_mode=request.args.get('image_mode')
    sortby=request.args.get('sortby')
    order=request.args.get('order')
    resp,total = FetchData(path=path,page=page,per_page=50,sortby=sortby,order=order,dismiss=True)
    if total=='files':
        return show(resp['id'])
    #是否有密码
    password,_,cur=has_item(path,'.password')
    md5_p=md5(path)
    has_verify_=has_verify(path)
    if request.method=="POST":
        password1=request.form.get('password')
        if password1==password:
            resp=make_response(redirect(url_for('.index',path=path)))
            resp.delete_cookie(md5_p)
            resp.set_cookie(md5_p,password)
            return resp
    if password!=False:
        if (not request.cookies.get(md5_p) or request.cookies.get(md5_p)!=password) and has_verify_==False:
            return render_template('password.html',path=path)
    readme,ext_r=GetReadMe(path)
    head,ext_d=GetHead(path)
    #设置cookies
    if image_mode:
        image_mode=request.args.get('image_mode',type=int)
    else:
        image_mode=request.cookies.get('image_mode') if request.cookies.get('image_mode') is not None else 0
        image_mode=int(image_mode)
    if sortby:
        sortby=request.args.get('sortby')
    else:
        sortby=request.cookies.get('sortby') if request.cookies.get('sortby') is not None else 'lastModtime'
        sortby=sortby
    if order:
        order=request.args.get('order')
    else:
        order=request.cookies.get('order') if request.cookies.get('order') is not None else 'desc'
        order=order
    #参数
    resp,total = FetchData(path=path,page=page,per_page=50,sortby=sortby,order=order,dismiss=True)
    pagination=Pagination(query=None,page=page, per_page=50, total=total, items=None)
    resp=make_response(render_template('index.html'
                    ,pagination=pagination
                    ,items=resp
                    ,path=path
                    ,image_mode=image_mode
                    ,readme=readme
                    ,ext_r=ext_r
                    ,head=head
                    ,ext_d=ext_d
                    ,sortby=sortby
                    ,order=order
                    ,endpoint='.index'))
    resp.set_cookie('image_mode',str(image_mode))
    resp.set_cookie('sortby',str(sortby))
    resp.set_cookie('order',str(order))
    return resp

@app.route('/file/<fileid>')
def show(fileid):
    name=GetName(fileid)
    ext=name.split('.')[-1].lower()
    path=GetPath(fileid)
    if request.method=='POST':
        url=request.url.replace(':80','').replace(':443','')
        if ext in ['csv','doc','docx','odp','ods','odt','pot','potm','potx','pps','ppsx','ppsxm','ppt','pptm','pptx','rtf','xls','xlsx']:
            downloadUrl=GetDownloadUrl(fileid)
            url = 'https://view.officeapps.live.com/op/view.aspx?src='+urllib.quote(downloadUrl)
            return redirect(url)
        elif ext in ['bmp','jpg','jpeg','png','gif']:
            return render_template('show/image.html',url=url,path=path)
        elif ext in ['mp4','webm']:
            return render_template('show/video.html',url=url,path=path)
        elif ext in ['mp4','webm','avi','mpg', 'mpeg', 'rm', 'rmvb', 'mov', 'wmv', 'mkv', 'asf']:
            return render_template('show/video2.html',url=url,path=path)
        elif ext in ['avi','mpg', 'mpeg', 'rm', 'rmvb', 'mov', 'wmv', 'mkv', 'asf']:
            return render_template('show/video2.html',url=url,path=path)
        elif ext in ['ogg','mp3','wav']:
            return render_template('show/audio.html',url=url,path=path)
        elif CodeType(ext) is not None:
            content=_remote_content(fileid)
            return render_template('show/code.html',content=content,url=url,language=CodeType(ext),path=path)
        else:
            downloadUrl=GetDownloadUrl(fileid)
            return redirect(downloadUrl)
    else:
        if 'no-referrer' in allow_site:
            downloadUrl=GetDownloadUrl(fileid)
            resp=redirect(downloadUrl)
            return resp
        elif sum([i in referrer for i in allow_site])>0:
            downloadUrl=GetDownloadUrl(fileid)
            return redirect(downloadUrl)
        else:
            return abort(404)

@app.route('/robot.txt')
def robot():
    resp="""
User-agent:  *
Disallow:  /
    """
    resp=make_response(resp)
    resp.headers['Content-Type'] = 'text/javascript; charset=utf-8'
    return resp


######################注册应用
from admin import admin as admin_blueprint
app.register_blueprint(admin_blueprint)


######################函数
app.jinja_env.globals['FetchData']=FetchData
app.jinja_env.globals['path_list']=path_list
app.jinja_env.globals['CanEdit']=CanEdit
app.jinja_env.globals['len']=len
app.jinja_env.globals['enumerate']=enumerate
app.jinja_env.globals['os']=os
app.jinja_env.globals['re']=re
app.jinja_env.globals['file_ico']=file_ico
app.jinja_env.globals['title']=title
app.jinja_env.globals['tj_code']=tj_code if tj_code is not None else ''
app.jinja_env.globals['allow_site']=','.join(allow_site)
app.jinja_env.globals['share_path']=share_path
app.jinja_env.globals['downloadUrl_timeout']=downloadUrl_timeout
################################################################################
#####################################启动#######################################
################################################################################
if __name__=='__main__':
    app.run(port=58693,debug=True)



