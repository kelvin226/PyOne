#-*- coding=utf-8 -*-
import json
import requests
import collections
import sys
if sys.version_info[0]==3:
    import urllib.parse as urllib
else:
    import urllib
import os
import re
import time
import shutil
import humanize
import StringIO
from dateutil.parser import parse
from Queue import Queue
from threading import Thread
from config import *
from pymongo import MongoClient
######mongodb
client = MongoClient('localhost',27017)
db=client.one2
items=db.items


#######授权链接
if od_type=='business':
    BaseAuthUrl='https://login.microsoftonline.com'
    ResourceID='https://api.office.com/discovery/'
elif od_type=='business_21v':
    BaseAuthUrl='https://login.partner.microsoftonline.cn'
    ResourceID='00000003-0000-0ff1-ce00-000000000000'

LoginUrl=BaseAuthUrl+'/common/oauth2/authorize?response_type=code\
&client_id={client_id}&redirect_uri={redirect_uri}'.format(client_id=client_id,redirect_uri=urllib.quote(redirect_uri))
OAuthUrl=BaseAuthUrl+'/common/oauth2/token'
AuthData='client_id={client_id}&redirect_uri={redirect_uri}&client_secret={client_secret}&code={code}&grant_type=authorization_code&resource={resource_id}'
ReFreshData='client_id={client_id}&redirect_uri={redirect_uri}&client_secret={client_secret}&refresh_token={refresh_token}&grant_type=refresh_token&resource={resource_id}'

headers={}

def convert2unicode(string):
    return string.encode('utf-8')

################################################################################
###################################授权函数#####################################
################################################################################


def OAuth(code):
    headers['Content-Type']='application/x-www-form-urlencoded'
    data=AuthData.format(client_id=client_id,redirect_uri=urllib.quote(redirect_uri),client_secret=client_secret,code=code,resource_id=ResourceID)
    url=OAuthUrl
    r=requests.post(url,data=data,headers=headers)
    return json.loads(r.text)

def ReFreshToken(refresh_token):
    app_url=GetAppUrl()
    headers['Content-Type']='application/x-www-form-urlencoded'
    data=ReFreshData.format(client_id=client_id,redirect_uri=urllib.quote(redirect_uri),client_secret=client_secret,refresh_token=refresh_token,resource_id=app_url)
    url=OAuthUrl
    r=requests.post(url,data=data,headers=headers)
    return json.loads(r.text)


def GetToken(Token_file='token.json'):
    if os.path.exists(os.path.join(config_dir,Token_file)):
        with open(os.path.join(config_dir,Token_file),'r') as f:
            token=json.load(f)
        try:
            if time.time()>int(token.get('expires_on')):
                print 'token timeout'
                refresh_token=token.get('refresh_token')
                token=ReFreshToken(refresh_token)
                if token.get('access_token'):
                    with open(os.path.join(config_dir,Token_file),'w') as f:
                        json.dump(token,f,ensure_ascii=False)
        except:
            with open(os.path.join(config_dir,'Atoken.json'),'r') as f:
                Atoken=json.load(f)
            refresh_token=Atoken.get('refresh_token')
            token=ReFreshToken(refresh_token)
            if token.get('access_token'):
                    with open(os.path.join(config_dir,Token_file),'w') as f:
                        json.dump(token,f,ensure_ascii=False)
        return token.get('access_token')
    else:
        return False

def GetAppUrl():
    global app_url
    if os.path.exists(os.path.join(config_dir,'AppUrl')):
        with open(os.path.join(config_dir,'AppUrl'),'r') as f:
            app_url=f.read().strip()
        return app_url
    else:
        # if od_type=='business':
        #     token=GetToken(Token_file='Atoken.json')
        #     print 'token:',token
        #     if token:
        #         header={'Authorization': 'Bearer {}'.format(token)}
        #         url='https://api.office.com/discovery/v2.0/me/services'
        #         r=requests.get(url,headers=header)
        #         retdata=json.loads(r.text)
        #         print retdata
        #         if retdata.get('value'):
        #             return retdata.get('value')[0]['serviceResourceId']
        #     return False
        # else:
        #     return app_url
        return app_url

################################################################################
###############################onedrive操作函数#################################
################################################################################
def GetExt(name):
    return name.split('.')[-1]

def Dir(path='/'):
    app_url=GetAppUrl()
    if path=='/':
        BaseUrl=app_url+'_api/v2.0/me/drive/root/children?expand=thumbnails'
        items.remove()
        GetItem(BaseUrl)
    else:
        grandid=0
        parent=''
        if path.endswith('/'):
            path=path[:-1]
        if path.startswith('/'):
            path=path[1:]
        if items.find_one({'grandid':0,'type':'folder'}):
            parent_id=0
            for idx,p in enumerate(path.split('/')):
                if parent_id==0:
                    parent_id=items.find_one({'name':p,'grandid':idx})['id']
                else:
                    parent_id=items.find_one({'name':p,'grandid':idx,'parent':parent_id})['id']
                items.delete_many({'parent':parent_id})
            grandid=idx+1
            parent=parent_id
        BaseUrl=app_url+'_api/v2.0/me/drive/root:/{}:/children?expand=thumbnails'.format(path)
        GetItem(url=BaseUrl,grandid=grandid,parent=parent)


def GetItem(url,grandid=0,parent=''):
    time.sleep(0.5) #避免过快
    app_url=GetAppUrl()
    token=GetToken()
    header={'Authorization': 'Bearer {}'.format(token)}
    trytime=1
    while 1:
        try:
            r=requests.get(url,headers=header)
            data=json.loads(r.content)
            values=data.get('value')
            #print url
            if len(values)>0:
                for value in values:
                    item={}
                    if value.get('folder'):
                        item['type']='folder'
                        item['name']=convert2unicode(value['name'])
                        item['id']=convert2unicode(value['id'])
                        item['size']=humanize.naturalsize(value['size'], gnu=True)
                        item['lastModtime']=humanize.naturaldate(parse(value['lastModifiedDateTime']))
                        item['grandid']=grandid
                        item['parent']=parent
                        subfodler=items.insert_one(item)
                        if value.get('folder').get('childCount')==0:
                            continue
                        else:
                            url=app_url+'_api/v2.0/me'+value.get('parentReference').get('path')+'/'+value.get('name')+':/children?expand=thumbnails'
                            GetItem(url,grandid+1,item['id'])
                    else:
                        item['type']='file'
                        item['name']=convert2unicode(value['name'])
                        item['id']=convert2unicode(value['id'])
                        item['size']=humanize.naturalsize(value['size'], gnu=True)
                        item['lastModtime']=humanize.naturaldate(parse(value['lastModifiedDateTime']))
                        item['grandid']=grandid
                        item['parent']=parent
                        items.insert_one(item)
            if data.get('@odata.nextLink'):
                GetItem(data.get('@odata.nextLink'),grandid,parent)
            break
        except Exception as e:
            trytime+=1
            print('error to opreate GetItem("{}","{}","{}"),try times :{}, reason: {}'.format(url,grandid,parent,trytime,e))
        if trytime>3:
            break


def UpdateFile():
    Dir(share_path)
    print('update file success!')


def FileExists(filename):
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token),'Content-Type':'application/json'}
    search_url=app_url+"_api/v2.0/me/drive/root/search(q='{}')".format(filename)
    r=requests.get(search_url,headers=headers)
    jsondata=json.loads(r.text)
    if len(jsondata['value'])==0:
        return False
    else:
        return True

################################################上传文件
def list_all_files(rootdir):
    import os
    _files = []
    flist = os.listdir(rootdir) #列出文件夹下所有的目录与文件
    for f in flist:
        path = os.path.join(rootdir,f)
        if os.path.isdir(path):
            _files.extend(list_all_files(path))
        if os.path.isfile(path):
            _files.append(path)
    return _files

def _filesize(path):
    size=os.path.getsize(path)
    # print('{}\'s size {}'.format(path,size))
    return size

def _file_content(path,offset,length):
    size=_filesize(path)
    offset,length=map(int,(offset,length))
    if offset>size:
        print('offset must smaller than file size')
        return False
    length=length if offset+length<size else size-offset
    endpos=offset+length-1 if offset+length<size else size-1
    # print("read file {} from {} to {}".format(path,offset,endpos))
    with open(path,'rb') as f:
        f.seek(offset)
        content=f.read(length)
    return content


def _upload(filepath,remote_path): #remote_path like 'share/share.mp4'
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token)}
    url=app_url+'_api/v2.0/me/drive/root:/'+remote_path+':/content'
    r=requests.put(url,headers=headers,data=open(filepath,'rb'))
    data=json.loads(r.content)
    if data.get('error'):
        print(data.get('error').get('message'))
        return False
    elif data.get('@content.downloadUrl'):
        print('upload success!')
        return data.get('@content.downloadUrl')
    else:
        print(data)
        return False

def _GetAllFile(parent_id="",parent_path="",filelist=[]):
    for f in db.items.find({'parent':parent_id}):
        if f['type']=='folder':
            _GetAllFile(f['id'],'/'.join([parent_path,f['name']]),filelist)
        else:
            fp='/'.join([parent_path,f['name']])
            if fp.startswith('/'):
                fp=base64.b64encode(fp[1:].encode('utf-8'))
            filelist.append(fp)
    return filelist


def CreateUploadSession(path):
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token),'Content-Type':'application/json'}
    url=app_url+'_api/v2.0/me/drive/root:/'+path+':/createUploadSession'
    data={
          "item": {
            "@microsoft.graph.conflictBehavior": "rename",
          }
        }
    try:
        r=requests.post(url,headers=headers,data=json.dumps(data))
        retdata=json.loads(r.content)
        if r.status_code==409:
            print('file exists')
            return False
        else:
            return retdata
    except Exception as e:
        print('error to opreate CreateUploadSession("{}"),reason {}'.format(path,e))
        return False

def UploadSession(uploadUrl, filepath, offset, length):
    token=GetToken()
    size=_filesize(filepath)
    offset,length=map(int,(offset,length))
    if offset>size:
        print('offset must smaller than file size')
        return False
    length=length if offset+length<size else size-offset
    endpos=offset+length-1 if offset+length<size else size-1
    print('upload file {} {}%'.format(filepath,round(float(endpos)/size*100,1)))
    filebin=_file_content(filepath,offset,length)
    headers={}
    # headers['Authorization']='bearer {}'.format(token)
    headers['Content-Length']=str(length)
    headers['Content-Range']='bytes {}-{}/{}'.format(offset,endpos,size)
    trytime=1
    while 1:
        try:
            r=requests.put(uploadUrl,headers=headers,data=filebin)
            data=json.loads(r.content)
            if r.status_code==202:
                offset=data.get('nextExpectedRanges')[0].split('-')[0]
                UploadSession(uploadUrl, filepath, offset, length)
            elif data.get('@content.downloadUrl'):
                print('upload success!')
                return data.get('@content.downloadUrl')
            else:
                print('upload fail')
                print(data.get('error').get('message'))
                r=requests.get(uploadUrl)
                if r.status_code==404:
                    print('please retry upload file {}'.format(filepath))
                    requests.delete(uploadUrl)
                    return False
                data=json.loads(r.content)
                if data.get('nextExpectedRanges'):
                    offset=data.get('nextExpectedRanges')[0].split('-')[0]
                    UploadSession(uploadUrl, filepath, offset, length)
                else:
                    print('please retry upload file {}'.format(filepath))
                    requests.delete(uploadUrl)
                    return False
            break
        except Exception as e:
            trytime+=1
            print('error to opreate UploadSession("{}","{}","{}","{}"), try times {}'.format(uploadUrl, filepath, offset, length,trytime))
        if trytime>3:
            requests.delete(uploadUrl)
            break
    return False

def Upload(filepath,remote_path=None):
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token),'Content-Type':'application/json'}
    if remote_path is None:
        remote_path=os.path.basename(filepath)
    elif remote_path.endswith('/'):
        remote_path=os.path.join(remote_path,os.path.basename(filepath))
    if remote_path.startswith('/'):
        remote_path=remote_path[1:]
    print('local file path:  {}\nremote file path:  {}'.format(filepath,remote_path))
    if _filesize(filepath)<10485760:
        print('upload small file')
        result=_upload(filepath,remote_path)
        if result!=False:
            print('upload success')
        else:
            print('upload fail')
    else:
        print('upload large file')
        session_data=CreateUploadSession(remote_path)
        if session_data==False:
            print('file exists')
        else:
            if session_data.get('uploadUrl'):
                uploadUrl=session_data.get('uploadUrl')
                length=327680*10
                offset=0
                UploadSession(uploadUrl,filepath,offset,length)
            else:
                print(session_data)
                print('create upload session fail! {}'.format(remote_path))
                return False


class MultiUpload(Thread):
    def __init__(self,waiting_queue):
        super(MultiUpload,self).__init__()
        self.queue=waiting_queue

    def run(self):
        while not self.queue.empty():
            localpath,remote_dir=self.queue.get()
            Upload(localpath,remote_dir)


def UploadDir(local_dir,remote_dir,threads=5):
    if not local_dir.endswith('/'):
        local_dir=local_dir+'/'
    print(u'geting file from dir {}'.format(local_dir))
    localfiles=list_all_files(local_dir)
    print(u'get {} files from dir {}'.format(len(localfiles),local_dir))
    print(u'check filename')
    for f in localfiles:
        dir_,fname=os.path.dirname(f),os.path.basename(f)
        if len(re.findall('[:/#]+',fname))>0:
            newf=os.path.join(dir_,re.sub('[:/#\|]+','',fname))
            shutil.move(f,newf)
    localfiles=list_all_files(local_dir)
    check_file_list=[]
    for file in localfiles:
        dir_,fname=os.path.dirname(file),os.path.basename(file)
        remote_path=remote_dir+'/'+dir_.replace(local_dir,'')+'/'+fname
        remote_path=remote_path.replace('//','/')
        check_file_list.append((remote_path,file))
    print(u'check repeat file')
    if remote_dir=='/':
        cloud_files=_GetAllFile()
    else:
        if remote_dir.startswith('/'):
            remote_dir=remote_dir[1:]
        if items.find_one({'grandid':0,'type':'folder','name':remote_dir.split('/')[0]}):
            parent_id=0
            parent_path=''
            for idx,p in enumerate(remote_dir.split('/')):
                if parent_id==0:
                    parent=items.find_one({'name':p,'grandid':idx})
                    parent_id=parent['id']
                    parent_path='/'.join([parent_path,parent['name']])
                else:
                    parent=items.find_one({'name':p,'grandid':idx,'parent':parent_id})
                    parent_id=parent['id']
                    parent_path='/'.join([parent_path,parent['name']])
            grandid=idx+1
            cloud_files=_GetAllFile(parent_id,parent_path)
    cloud_files=dict([(i,i) for i in cloud_files])
    queue=Queue()
    tasks=[]
    for remote_path,file in check_file_list:
        if not cloud_files.get(base64.b64encode(remote_path)):
            queue.put((file,remote_path))
    print "check_file_list {},cloud_files {},queue {}".format(len(check_file_list),len(cloud_files),queue.qsize())
    for i in range(min(threads,queue.qsize())):
        t=MultiUpload(queue)
        t.start()
        tasks.append(t)
    for t in tasks:
        t.join()





########################
def CheckTimeOut(fileid):
    app_url=GetAppUrl()
    token=GetToken()
    headers={'Authorization':'bearer {}'.format(token),'Content-Type':'application/json'}
    url=app_url+'_api/v2.0/me/drive/items/'+fileid
    r=requests.get(url,headers=headers)
    data=json.loads(r.content)
    if data.get('@content.downloadUrl'):
        downloadUrl=data.get('@content.downloadUrl')
        start_time=time.time()
        for i in range(10000):
            r=requests.head(downloadUrl)
            print '{}\'s gone, status:{}'.format(time.time()-start_time,r.status_code)
            if r.status_code==404:
                break




if __name__=='__main__':
    func=sys.argv[1]
    if len(sys.argv)>2:
        args=sys.argv[2:]
        eval(func+str(tuple(args)))
    else:
        eval(func+'()')
