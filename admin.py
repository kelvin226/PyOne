#-*- coding=utf-8 -*-
from flask import Blueprint,redirect,url_for,request,render_template,flash,session,jsonify,Response,make_response
from flask_sqlalchemy import Pagination
from function import *
from config import *
from run import FetchData,path_list,GetName,CodeType,_remote_content,rd,has_item,AddResource
import os
import io
import re
import subprocess
import random
import urllib
from shelljob import proc
import eventlet

eventlet.monkey_patch()


admin = Blueprint('admin', __name__,url_prefix='/admin')

############功能函数
def set(key,value):
    allow_key=['title','share_path','downloadUrl_timeout','allow_site','password','client_secret','client_id','tj_code']
    if key not in allow_key:
        return u'禁止修改'
    print 'set {}:{}'.format(key,value)
    config_path=os.path.join(config_dir,'config.py')
    with open(config_path,'r') as f:
        old_text=f.read()
    with open(config_path,'w') as f:
        if len(re.findall(key,old_text))>0:
            if key=='allow_site':
                value=value.split(',')
                new_text=re.sub('{}=.*'.format(key),'{}={}'.format(key,value),old_text)
            elif key=='tj_code':
                new_text=re.sub('{}=.*'.format(key),'{}="""{}"""'.format(key,value),old_text)
            else:
                new_text=re.sub('{}=.*'.format(key),'{}="{}"'.format(key,value),old_text)
        else:
            if key=='allow_site':
                value=value.split(',')
                new_text=old_text+'\n\n{}={}'.format(key,value)
            elif key=='tj_code':
                new_text=re.sub('{}=.*'.format(key),'{}="""{}"""'.format(key,value),old_text)
            else:
                new_text=old_text+'\n\n{}="{}"'.format(key,value)
        f.write(new_text)


############视图函数
@admin.before_request
def before_request():
    if request.endpoint.startswith('admin') and request.endpoint!='admin.login' and request.endpoint!='admin.install' and session.get('login') is None:
        return redirect(url_for('admin.login'))


########web console
@admin.route('/web_console')
def web_console():
    g = proc.Group()
    action=request.args.get('action')
    allow_action=['UpdateFile','UploadDir','Upload']
    if action not in allow_action:
        return make_response('error')
    if action in ['UploadDir','Upload']:
        local=urllib.unquote(request.args.get('local'))
        remote=urllib.unquote(request.args.get('remote'))
        cmd=["python","-u",os.path.join(config_dir,'function.py'),action,local,remote]
    elif action=='UpdateFile':
        dir_=request.args.get('dir')
        if dir_=='/':
            cmd=["python","-u",os.path.join(config_dir,'function.py'),action]
        else:
            cmd=["python","-u",os.path.join(config_dir,'function.py'),'Dir',dir_]
    else:
        cmd=["python","-u",os.path.join(config_dir,'function.py'),action]
    p = g.run(cmd)
    def read_process():
        while g.is_pending():
            lines = g.readlines()
            for proc, line in lines:
                yield "data:" + line + "\n\n"
        yield "data:end\n\n"
    return Response(read_process(), mimetype= 'text/event-stream')

########admin
@admin.route('/',methods=['GET','POST'])
@admin.route('/setting',methods=['GET','POST'])
def setting():
    if request.method=='POST':
        title=request.form.get('title','PyOne')
        share_path=request.form.get('share_path','/')
        downloadUrl_timeout=request.form.get('downloadUrl_timeout',5*60)
        allow_site=request.form.get('allow_site','no-referrer')
        tj_code=request.form.get('tj_code','')
        password1=request.form.get('password1')
        password2=request.form.get('password2')
        new_password=password
        if ((password1 is not None and password2 is None) or (password1 is None and password2 is not None)):
            flash(u'请输入新密码或者二次确认新密码')
        elif password1 is not None and password2 is not None and password1!=password2:
            flash(u'两次输入密码不相同')
        elif password1 is not None and password2 is not None and password1==password2 and password1!='':
            new_password=password1
        set('title',title)
        set('downloadUrl_timeout',downloadUrl_timeout)
        set('share_path',share_path)
        set('allow_site',allow_site)
        set('tj_code',tj_code)
        set('password',new_password)
        reload()
        return render_template('admin/setting.html')
    return render_template('admin/setting.html')




@admin.route('/upload',methods=["POST","GET"])
def upload():
    if request.method=='POST':
        local=request.form.get('local')
        remote=request.form.get('remote')
        if not os.path.exists(local):
            flash('本地目录/文件不存在')
            return redirect(url_for('admin.upload'))
        if os.path.isfile(local):
            action='Upload'
        else:
            action='UploadDir'
        return render_template('admin/upload.html',remote=remote,local=local,action=action)
    return render_template('admin/upload.html')



@admin.route('/cache',methods=["POST","GET"])
def cache():
    if request.method=='POST':
        dir_=request.form.get('dir')
        return render_template('admin/cache.html',dir=dir_,action='UpdateFile')
    return render_template('admin/cache.html')


@admin.route('/manage',methods=["POST","GET"])
def manage():
    if request.method=='POST':
        pass
    path=urllib.unquote(request.args.get('path','/'))
    if path=='':
        path='/'
    if path!='/' and path.startswith('/'):
        path=re.sub('^/+','',path)
    page=request.args.get('page',1,type=int)
    image_mode=request.args.get('image_mode')
    sortby=request.args.get('sortby')
    order=request.args.get('order')
    if sortby:
        sortby=request.args.get('sortby')
    else:
        sortby=request.cookies.get('admin_sortby') if request.cookies.get('admin_sortby') is not None else 'lastModtime'
        sortby=sortby
    if order:
        order=request.args.get('order')
    else:
        order=request.cookies.get('admin_order') if request.cookies.get('admin_order') is not None else 'desc'
        order=order
    resp,total = FetchData(path=path,page=page,per_page=50,sortby=sortby,order=order)
    pagination=Pagination(query=None,page=page, per_page=50, total=total, items=None)
    resp=make_response(render_template('admin/manage.html',pagination=pagination,items=resp,path=path,sortby=sortby,order=order,endpoint='admin.manage'))
    resp.set_cookie('admin_sortby',str(sortby))
    resp.set_cookie('admin_order',str(order))
    return resp


@admin.route('/edit',methods=["GET","POST"])
def edit():
    if request.method=='POST':
        fileid=request.form.get('fileid')
        content=request.form.get('content').encode('utf-8')
        info={}
        token=GetToken()
        app_url=GetAppUrl()
        headers={'Authorization':'bearer {}'.format(token)}
        url=app_url+'v1.0/me/drive/items/{}/content'.format(fileid)
        try:
            r=requests.put(url,headers=headers,data=content,timeout=10)
            data=json.loads(r.content)
            if data.get('id'):
                info['status']=0
                info['msg']='修改成功'
                rd.delete('{}:content'.format(fileid))
                file=items.find_one({'id':fileid})
                name=file['name']
                path=file['path'].replace('/'+name,'').replace(name,'')
                if path=='':
                    path='/'
                key='has_item$#$#$#$#{}$#$#$#$#{}'.format(path,name)
                rd.delete(key)
            else:
                info['status']=0
                info['msg']=data.get('error').get('message')
        except Exception as e:
            print e
            info['status']=0
            info['msg']='修改超时'
        return jsonify(info)
    fileid=request.args.get('fileid')
    name=GetName(fileid)
    ext=name.split('.')[-1]
    language=CodeType(ext)
    if language is None:
        language='Text'
    content=_remote_content(fileid)
    return render_template('admin/edit.html',content=content,fileid=fileid,name=name,language=language)

###本地上传文件只onedrive，通过服务器中转
@admin.route('/upload_local',methods=['POST','GET'])
def upload_local():
    remote_folder=request.args.get('path')
    return render_template('admin/upload_local.html',remote_folder=remote_folder)

@admin.route('/checkChunk', methods=['POST'])
def checkChunk():
    md5=request.form.get('fileMd5')
    fileName=request.form.get('name')
    chunk=request.form.get('chunk',0,type=int)
    filename = './upload/{}-{}'.format(fileName, chunk)
    if os.path.exists(filename):
        exists=True
    else:
        exists=False
    return jsonify({'ifExist':exists})


@admin.route('/mergeChunks', methods=['POST'])
def mergeChunks():
    fileName=request.form.get('fileName')
    md5=request.form.get('fileMd5')
    chunk = 0  # 分片序号
    with open(u'./upload/{}'.format(fileName), 'wb') as target_file:  # 创建新文件
        while True:
            try:
                filename = './upload/{}-{}'.format(fileName, chunk)
                source_file = open(filename, 'rb')  # 按序打开每个分片
                target_file.write(source_file.read())  # 读取分片内容写入新文件
                source_file.close()
            except IOError as msg:
                break
            chunk += 1
            os.remove(filename)  # 删除该分片，节约空间
    return jsonify({'upload':True})


@admin.route('/recv_upload', methods=['POST'])
def recv_upload():  # 接收前端上传的一个分片
    md5=request.form.get('fileMd5')
    name=request.form.get('name')
    chunk_id=request.form.get('chunk',0,type=int)
    filename = '{}-{}'.format(name,chunk_id)
    upload_file = request.files['file']
    upload_file.save('./upload/{}'.format(filename))
    return jsonify({'upload_part':True})


@admin.route('/to_one',methods=['GET'])
def server_to_one():
    filename=request.args.get('filename').encode('utf-8')
    remote_folder=request.args.get('remote_folder').encode('utf-8')
    if remote_folder!='/':
        remote_folder=remote_folder+'/'
    local_dir=os.path.join(config_dir,'upload')
    filepath=urllib.unquote(os.path.join(local_dir,filename))
    _upload_session=Upload_for_server(filepath,remote_folder)
    def read_status():
        while 1:
            try:
                msg=_upload_session.next()['status']
                yield "data:" + msg + "\n\n"
            except Exception as e:
                msg='end'
                yield "data:" + msg + "\n\n"
                os.remove(filepath)
                break
    return Response(read_status(), mimetype= 'text/event-stream')


###本地上传文件只onedrive，通过服务器中转



@admin.route('/setFile',methods=["GET","POST"])
@admin.route('/setFile/<filename>',methods=["GET","POST"])
def setFile(filename=None):
    if request.method=='POST':
        path=request.form.get('path')
        filename=request.form.get('filename')
        if not path.startswith('/'):
            path='/'+path
        remote_file=os.path.join(path,filename)
        content=request.form.get('content').encode('utf-8')
        info={}
        token=GetToken()
        app_url=GetAppUrl()
        headers={'Authorization':'bearer {}'.format(token)}
        url=app_url+'v1.0/me/drive/items/root:{}:/content'.format(remote_file)
        try:
            r=requests.put(url,headers=headers,data=content,timeout=10)
            data=json.loads(r.content)
            if data.get('id'):
                AddResource(data)
                info['status']=0
                info['msg']='添加成功'
                if path.startswith('/') and path!='/':
                    path=path[1:]
                key='has_item$#$#$#$#{}$#$#$#$#{}'.format(path,filename)
                print key
                rd.delete(key)
            else:
                info['status']=0
                info['msg']=data.get('error').get('message')
        except Exception as e:
            info['status']=0
            info['msg']='超时'
        return jsonify(info)
    path=urllib.unquote(request.args.get('path'))
    _,fid,i=has_item(path,filename)
    if fid!=False:
        return redirect(url_for('admin.edit',fileid=fid))
    return render_template('admin/setpass.html',path=path,filename=filename)


@admin.route('/delete',methods=["POST"])
def delete():
    ids=request.form.get('id')
    if ids is None:
        return jsonify({'msg':u'请选择要删除的文件','status':0})
    ids=ids.split('##')
    infos={}
    infos['status']=1
    infos['delete']=0
    infos['fail']=0
    for id in ids:
        status=DeleteRemoteFile(id)
        if status:
            infos['delete']+=1
        else:
            infos['fail']+=1
    return jsonify(infos)



@admin.route('/login',methods=["POST","GET"])
def login():
    if request.method=='POST':
        password1=request.form.get('password')
        if password1==password:
            session['login']='true'
            return redirect(url_for('admin.setting'))
        else:
            return render_template('admin/login.html')
    return render_template('admin/login.html')


@admin.route('/logout',methods=['GET','POST'])
def logout():
    session.pop('login',None)
    return redirect('/')

@admin.route('/reload',methods=['GET','POST'])
def reload():
    cmd='supervisorctl -c {} restart pyone'.format(os.path.join(config_dir,'supervisord.conf'))
    subprocess.Popen(cmd,shell=True)
    flash('正在重启网站...')
    return redirect(url_for('admin.setting'))




###########################################安装
@admin.route('/install',methods=['POST','GET'])
def install():
    if items.count()>0 or os.path.exists(os.path.join(config_dir,'data/token.json')):
        return redirect('/')
    if request.method=='POST':
        step=request.form.get('step',type=int)
        if step==1:
            client_secret=request.form.get('client_secret')
            client_id=request.form.get('client_id')
            redirect_uri='https://auth.3pp.me'
            set('client_secret',client_secret)
            set('client_id',client_id)
            login_url=LoginUrl.format(client_id=client_id,redirect_uri=redirect_uri)
            return render_template('admin/install_1.html',client_secret=client_secret,client_id=client_id,login_url=login_url)
        else:
            client_secret=request.form.get('client_secret')
            client_id=request.form.get('client_id')
            code=request.form.get('code')
            redirect_uri='https://auth.3pp.me'
            #授权
            headers['Content-Type']='application/x-www-form-urlencoded'
            data=AuthData.format(client_id=client_id,redirect_uri=urllib.quote(redirect_uri),client_secret=client_secret,code=code)
            url=OAuthUrl
            r=requests.post(url,data=data,headers=headers)
            Atoken=json.loads(r.text)
            if Atoken.get('access_token'):
                with open(os.path.join(config_dir,'data/Atoken.json'),'w') as f:
                    json.dump(Atoken,f,ensure_ascii=False)
                app_url=GetAppUrl()
                refresh_token=Atoken.get('refresh_token')
                with open(os.path.join(config_dir,'data/AppUrl'),'w') as f:
                    f.write(app_url)
                token=ReFreshToken(refresh_token)
                with open(os.path.join(config_dir,'data/token.json'),'w') as f:
                    json.dump(token,f,ensure_ascii=False)
                return make_response('<h1>授权成功!<a href="/">点击进入首页</a><br>请在后台另开一个ssh窗口，运行：<pre>python function.py UpdateFile</pre>进行更新数据操作</h1>')
            else:
                return jsonify(Atoken)
    resp=render_template('admin/install_0.html',step=1)
    return resp

