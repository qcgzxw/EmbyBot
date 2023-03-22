import asyncio
import re

from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus
import requests
import json
import string
import pandas as pd
from sqlalchemy import create_engine
import time
import uuid
import random
from datetime import datetime, timedelta
from config import *

app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)  # create tg bot
engine = create_engine(
    f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}',
    pool_size=20,
    pool_recycle=3600
)
pd_invite_code = None
pd_config = None
pd_user = None

tg_group_members = {}
tg_group_administrators = {}
tg_channel_members = {}


def db_execute(raw=''):
    if raw == '':
        return

    with engine.connect() as connection:
        result = connection.execute(raw)
        return result


def pd_read_sql_query(raw=''):
    with engine.connect() as conn:
        return pd.read_sql_query(raw, conn)


def pd_to_sql(df_write, table, **kwargs):
    df_write.to_sql(table, engine, **kwargs)


def IsAdmin(telegram_id: int):  # TODO change it in database
    for i in range(0, len(admin_list)):
        if telegram_id == admin_list[i]:
            return True
    return False


def IsGroupAdmin(telegram_id: int):
    global tg_group_administrators
    return telegram_id in tg_group_administrators.keys()


def LocalTime(time=''):
    n_LastLogin = time[0:19]
    UTC_FORMAT = "%Y-%m-%dT%H:%M:%S"
    utcTime_LastLogin = datetime.strptime(n_LastLogin, UTC_FORMAT)
    localtime_LastLogin = utcTime_LastLogin + timedelta(hours=8)
    return localtime_LastLogin  # change emby time to Asia/Shanghai time


def ReplyToMessageFromUserId(message: Message) -> int:
    if message.reply_to_message is None or message.reply_to_message.from_user is None:
        return 0
    return message.reply_to_message.from_user.id


async def CreateCode(telegram_id: int):
    if IsAdmin(telegram_id) or IsGroupAdmin(telegram_id):  # If you are administrator, you can create a code
        code = f'embyplus-{str(uuid.uuid4())}'
        df_write = pd.DataFrame({'code': code, 'tgid': telegram_id, 'time': int(time.time()), 'used': 'F'}, index=[0])
        pd_to_sql(df_write, 'invite_code', index=False, if_exists='append')
        return code
    else:
        return 'A'  # not an admin that cannot use this command


async def invite(message: Message):
    tgid = message.from_user.id
    global pd_user
    global pd_invite_code
    pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
    pd_user = pd_read_sql_query('SELECT * FROM user;')
    if canrig(telegram_id=message.from_user.id) == 'B' or hadname(message.from_user.id) == 'B':
        return 'D'  # have an account or have the chance to register
    pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
    pd_user = pd_read_sql_query('SELECT * FROM user;')
    message = str(message.text).split(' ')
    code = message[-1]  # get the code
    code_find = (pd_invite_code['code'] == code)
    code = (pd_invite_code[code_find]['code'])
    code = code.to_list()
    try:
        code = code[-1]  # find the code if it is in the database
    except IndexError:
        return 'A'
    used = (pd_invite_code[code_find]['used'])
    used = used.to_list()
    used = used[-1]
    if used == 'T':
        return 'B'  # the code has been used
    else:
        code_used = f"UPDATE `{db_name}`.`invite_code` SET `used`='T' WHERE `code`='{code}';"
        db_execute(code_used)  # set the code has been used
        pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
        pd_user = pd_read_sql_query('SELECT * FROM user;')
        tgid_find = (pd_user['tgid'] == tgid)
        try:
            tgid = int(pd_user[tgid_find]['tgid'])  # find the tgid if the user is in the databse
        except TypeError:
            df_write = pd.DataFrame({'tgid': tgid, 'admin': 'F', 'canrig': 'T'}, index=[0])
            pd_to_sql(df_write, 'user', index=False, if_exists='append')  # add the user info
            pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
            pd_user = pd_read_sql_query('SELECT * FROM user;')
            return 'C'
        setcanrig = f"UPDATE `{db_name}`.`user` SET `canrig`='T' WHERE `tgid`='{message.from_user.id}';"
        db_execute(setcanrig)  # update the status that can register
        pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
        pd_user = pd_read_sql_query('SELECT * FROM user;')
        return 'C'  # done


def canrig(telegram_id: int):
    global pd_user
    global pd_invite_code
    pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
    pd_user = pd_read_sql_query('SELECT * FROM user;')
    tgid_find = (pd_user['tgid'] == telegram_id)
    tgid = (pd_user[tgid_find]['tgid'])
    tgid = tgid.to_list()
    try:
        tgid = tgid[-1]
    except IndexError:
        return 'A'  # not in the database
    sqlcanrig = (pd_user[tgid_find]['canrig'])
    sqlcanrig = sqlcanrig.to_list()
    sqlcanrig = sqlcanrig[-1]
    sqlemby_name = (pd_user[tgid_find]['emby_name'])
    sqlemby_name = sqlemby_name.to_list()
    sqlemby_name = sqlemby_name[-1]
    if sqlcanrig == 'T':
        return 'B'  # can register
    else:
        return 'C'  # cannot register


def hadname(telegram_id: int):
    global pd_user
    global pd_invite_code
    pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
    pd_user = pd_read_sql_query('SELECT * FROM user;')
    tgid_find = (pd_user['tgid'] == telegram_id)
    tgid = (pd_user[tgid_find]['tgid'])
    tgid = tgid.to_list()
    try:
        tgid = tgid[-1]
    except IndexError:
        return 'A'  # not in the database
    sqlemby_name = (pd_user[tgid_find]['emby_name'])
    sqlemby_name = sqlemby_name.to_list()
    sqlemby_name = sqlemby_name[-1]
    if sqlemby_name != 'None':
        return 'B'  # have an account
    else:
        return 'C'  # does not have an account


# TODO put the time into the database
async def register_all_time(message: Message):  # public register
    if IsAdmin(message.from_user.id):
        message = str(message.text).split(' ')
        if len(message) == 1:
            return 'B'
        message = message[-1]
        write_config(config='register_public', params='True')
        write_config(config='register_public_time', params=str(int(time.time()) + (int(message) * 60)))
        write_config(config='register_method', params='Time')
        return int(time.time()) + (int(message) * 60)
    else:
        return 'A'  # not an admin


# TODO put the user into the database
async def register_all_user(message: Message):
    if IsAdmin(message.from_user.id):
        message = str(message.text).split(' ')
        if len(message) == 1:
            return 'B'
        message = message[-1]

        write_config(config='register_public', params='True')
        write_config(config='register_public_user', params=str(int(message)))
        write_config(config='register_method', params='User')
        return int(message)
    else:
        return 'A'  # not an admin


def userinfo(telegram_id: int):
    global pd_user
    global pd_invite_code
    pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
    pd_user = pd_read_sql_query('SELECT * FROM user;')
    tgid_find = (pd_user['tgid'] == telegram_id)
    tgid_a = (pd_user[tgid_find]['tgid'])
    tgid_a = tgid_a.to_list()
    try:
        telegram_id = tgid_a[-1]
    except IndexError:
        return 'NotInTheDatabase'
    emby_name = (pd_user[tgid_find]['emby_name'])
    emby_name = emby_name.to_list()
    emby_name = emby_name[-1]
    emby_id = (pd_user[tgid_find]['emby_id'])
    emby_id = emby_id.to_list()
    emby_id = emby_id[-1]
    canrig = (pd_user[tgid_find]['canrig'])
    canrig = canrig.to_list()
    canrig = canrig[-1]
    bantime = (pd_user[tgid_find]['bantime'])
    bantime = bantime.to_list()
    bantime = bantime[-1]
    if bantime == 0:
        bantime = 'None'
    else:
        expired = time.localtime(bantime)
        expired = time.strftime("%Y/%m/%d %H:%M:%S", expired)  # change the time format
        bantime = expired
    if emby_name != 'None':
        r = requests.get(f"{embyurl}/emby/users/{emby_id}?api_key={embyapi}").text
        try:
            r = json.loads(r)
            lastacttime = r['LastActivityDate']
            createdtime = r['DateCreated']
            lastacttime = LocalTime(time=lastacttime)
            createdtime = LocalTime(time=createdtime)
        except json.decoder.JSONDecodeError:
            return 'NotInTheDatabase'
        except KeyError:
            lastacttime = 'None'
            createdtime = 'None'
        return 'HaveAnEmby', emby_name, emby_id, lastacttime, createdtime, bantime
    else:
        return 'NotHaveAnEmby', canrig


def prichat(message: Message):
    if str(message.chat.type) == 'ChatType.PRIVATE':
        return True
    else:
        return False


async def BanEmby(message: Message, replyid=0):
    telegram_id = message.from_user.id
    if IsAdmin(telegram_id):
        if hadname(replyid) == 'B':
            global pd_user
            global pd_invite_code
            pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
            pd_user = pd_read_sql_query('SELECT * FROM user;')
            tgid_find = (pd_user['tgid'] == replyid)
            tgid_a = (pd_user[tgid_find]['tgid'])
            tgid_a = tgid_a.to_list()
            try:
                tgid = tgid_a[-1]
            except IndexError:
                return 'NotInTheDatabase'
            emby_name = (pd_user[tgid_find]['emby_name'])
            emby_name = emby_name.to_list()
            emby_name = emby_name[-1]
            emby_id = (pd_user[tgid_find]['emby_id'])
            emby_id = emby_id.to_list()
            emby_id = emby_id[-1]
            params = (('api_key', embyapi),
                      )
            headers = {
                'accept': 'application/json',
                'Content-Type': 'application/json',
            }
            data = '''{
                "IsAdministrator": false,
                "IsHidden": true,
                "IsHiddenRemotely": true,
                "IsDisabled": true,
                "EnableRemoteControlOfOtherUsers": false,
                "EnableSharedDeviceControl": false,
                "EnableRemoteAccess": true,
                "EnableLiveTvManagement": false,
                "EnableLiveTvAccess": true,
                "EnableMediaPlayback": true,
                "EnableAudioPlaybackTranscoding": false,
                "EnableVideoPlaybackTranscoding": false,
                "EnablePlaybackRemuxing": false,
                "EnableContentDeletion": false,
                "EnableContentDownloading": false,
                "EnableSubtitleDownloading": false,
                "EnableSubtitleManagement": false,
                "EnableSyncTranscoding": false,
                "EnableMediaConversion": false,
                "EnableAllDevices": true,
                "SimultaneousStreamLimit": 3
            }'''
            resp = requests.post(embyurl + '/emby/Users/' + emby_id + '/Policy',
                                 headers=headers,
                                 params=params, data=data)  # update policy
            setbantime = f"UPDATE `{db_name}`.`user` SET `bantime`={int(time.time())} WHERE `tgid`='{telegram_id}';"
            db_execute(setbantime)  # update the status that cannot register
            return 'A', emby_name  # Ban the user's emby account
        else:
            if canrig(telegram_id=replyid):
                setcanrig = f"UPDATE `{db_name}`.`user` SET `canrig`='F' WHERE `tgid`='{replyid}';"
                db_execute(setcanrig)  # update the status that cannot register
                return 'C', 'CannotReg'  # set cannot register
            else:
                return 'D', 'DoNothing'  # do nothing
    else:
        return 'B', 'NotAnAdmin'  # Not an admin


async def UnbanEmby(message: Message, replyid=0):
    if IsAdmin(message.from_user.id):
        if hadname(replyid) == 'B':
            global pd_user
            global pd_invite_code
            pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
            pd_user = pd_read_sql_query('SELECT * FROM user;')
            tgid_find = (pd_user['tgid'] == replyid)
            tgid_a = (pd_user[tgid_find]['tgid'])
            tgid_a = tgid_a.to_list()
            try:
                tgid = tgid_a[-1]
            except IndexError:
                return 'NotInTheDatabase'
            emby_id = (pd_user[tgid_find]['emby_id'])
            emby_id = emby_id.to_list()
            emby_id = emby_id[-1]
            emby_name = (pd_user[tgid_find]['emby_name'])
            emby_name = emby_name.to_list()
            emby_name = emby_name[-1]
            params = (('api_key', embyapi),
                      )
            headers = {
                'accept': 'application/json',
                'Content-Type': 'application/json',
            }
            data = '''{
                "IsAdministrator": false,
                "IsHidden": true,
                "IsHiddenRemotely": true,
                "IsDisabled": false,
                "EnableRemoteControlOfOtherUsers": false,
                "EnableSharedDeviceControl": false,
                "EnableRemoteAccess": true,
                "EnableLiveTvManagement": false,
                "EnableLiveTvAccess": true,
                "EnableMediaPlayback": true,
                "EnableAudioPlaybackTranscoding": false,
                "EnableVideoPlaybackTranscoding": false,
                "EnablePlaybackRemuxing": false,
                "EnableContentDeletion": false,
                "EnableContentDownloading": false,
                "EnableSubtitleDownloading": false,
                "EnableSubtitleManagement": false,
                "EnableSyncTranscoding": false,
                "EnableMediaConversion": false,
                "EnableAllDevices": true,
                "SimultaneousStreamLimit": 3
            }'''
            resp = requests.post(embyurl + '/emby/Users/' + emby_id + '/Policy',
                                 headers=headers,
                                 params=params, data=data)  # update policy
            setbantime = f"UPDATE `{db_name}`.`user` SET `bantime`={0} WHERE `tgid`='{message.from_user.id}';"
            db_execute(setbantime)  # update the status that cannot register
            return 'A', emby_name  # Unban the user's emby account
        else:
            return 'C', 'DoNothing'  # do nothing
    else:
        return 'B', 'NotAnAdmin'  # Not an admin


async def create(message: Message):  # register with invite code
    global pd_user
    global pd_invite_code
    tgid = message.from_user.id
    pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
    pd_user = pd_read_sql_query('SELECT * FROM user;')
    if hadname(message.from_user.id) == 'B':
        return 'A'  # already have an account
    if canrig(message.from_user.id) != 'B':
        return 'C'  # cannot register
    message = str(message.text).split(' ')
    name = message[-1]
    name = "" if re.match('[a-zA-Z0-9_-]+', name) is None else re.match('[a-zA-Z0-9_-]+', name).group()
    if name == '' or len(name) < 5:
        return 'B'  # do not input a name
    data = '{"Name":"' + name + '","HasPassword":true}'
    params = (('api_key', embyapi),
              )
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
    }
    r = requests.post(url=embyurl + '/emby/Users/New', headers=headers, params=params, data=data).text
    try:
        r = json.loads(r)  # create a new user
    except json.decoder.JSONDecodeError:
        if r.find('already exists.'):
            return 'D'  # already exists
    data1 = '''{
                "IsAdministrator": false,
                "IsHidden": true,
                "IsHiddenRemotely": true,
                "IsDisabled": false,
                "EnableRemoteControlOfOtherUsers": false,
                "EnableSharedDeviceControl": false,
                "EnableRemoteAccess": true,
                "EnableLiveTvManagement": false,
                "EnableLiveTvAccess": true,
                "EnableMediaPlayback": true,
                "EnableAudioPlaybackTranscoding": false,
                "EnableVideoPlaybackTranscoding": false,
                "EnablePlaybackRemuxing": false,
                "EnableContentDeletion": false,
                "EnableContentDownloading": false,
                "EnableSubtitleDownloading": false,
                "EnableSubtitleManagement": false,
                "EnableSyncTranscoding": false,
                "EnableMediaConversion": false,
                "EnableAllDevices": true,
                "SimultaneousStreamLimit": 3
            }'''
    requests.post(embyurl + '/emby/Users/' + r['Id'] + '/Policy', headers=headers,
                  params=params, data=data1)  # update policy
    NewPw = ''.join(random.sample(string.ascii_letters + string.digits, 8))
    data = '{"CurrentPw":"" , "NewPw":"' + NewPw + '","ResetPassword" : false}'
    requests.post(f"{embyurl}/emby/users/{r['Id']}/Password?api_key={embyapi}", headers=headers, data=data)
    pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
    pd_user = pd_read_sql_query('SELECT * FROM user;')
    tgid_find = (pd_user['tgid'] == tgid)
    tgid_a = (pd_user[tgid_find]['tgid'])
    tgid_a = tgid_a.to_list()
    tgid_find = (pd_user['tgid'] == tgid)
    try:
        tgid_a = int(pd_user[tgid_find][
                         'tgid'])  # find the tgid if the user is in the databse
    except TypeError:
        df_write = pd.DataFrame(
            {'tgid': tgid, 'admin': 'F', 'emby_name': str(r['Name']),
             'emby_id': str(r['Id']), 'canrig': 'F'}, index=[0])
        pd_to_sql(df_write, 'user', index=False, if_exists='append')  # add the user info
        return r['Name'], NewPw
    sqlemby_name = f"UPDATE `{db_name}`.`user` SET `emby_name`='{r['Name']}' WHERE `tgid`='{tgid}';"
    sqlcanrig = f"UPDATE `{db_name}`.`user` SET `canrig`='F' WHERE `tgid`={tgid};"
    sqlemby_id = f"UPDATE `{db_name}`.`user` SET `emby_id`='{r['Id']}' WHERE `tgid`='{tgid}';"
    db_execute(sqlcanrig)
    db_execute(sqlemby_name)
    db_execute(sqlemby_id)
    pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
    pd_user = pd_read_sql_query('SELECT * FROM user;')
    return r['Name'], NewPw


async def create_time(message: Message):
    global pd_user
    global pd_invite_code
    tgid = message.from_user.id
    register_public_time = load_config('register_public_time')
    if int(time.time()) < register_public_time:
        pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
        pd_user = pd_read_sql_query('SELECT * FROM user;')
        if hadname(tgid) == 'B':
            return 'A'  # already have an account
        message = str(message.text).split(' ')
        name = message[-1]
        if name == '' or name == ' ':
            return 'B'  # do not input a name
        data = '{"Name":"' + name + '","HasPassword":true}'
        params = (('api_key', embyapi),
                  )
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
        }
        r = requests.post(url=embyurl + '/emby/Users/New', headers=headers,
                          params=params, data=data).text
        try:
            r = json.loads(r)  # create a new user
        except json.decoder.JSONDecodeError:
            if r.find('already exists.'):
                return 'D'  # already exists
        data1 = '''{
            "IsAdministrator": false,
            "IsHidden": true,
            "IsHiddenRemotely": true,
            "IsDisabled": false,
            "EnableRemoteControlOfOtherUsers": false,
            "EnableSharedDeviceControl": false,
            "EnableRemoteAccess": true,
            "EnableLiveTvManagement": false,
            "EnableLiveTvAccess": true,
            "EnableMediaPlayback": true,
            "EnableAudioPlaybackTranscoding": false,
            "EnableVideoPlaybackTranscoding": false,
            "EnablePlaybackRemuxing": false,
            "EnableContentDeletion": false,
            "EnableContentDownloading": false,
            "EnableSubtitleDownloading": false,
            "EnableSubtitleManagement": false,
            "EnableSyncTranscoding": false,
            "EnableMediaConversion": false,
            "EnableAllDevices": true,
            "SimultaneousStreamLimit": 3
        }'''
        requests.post(embyurl + '/emby/Users/' + r['Id'] + '/Policy',
                      headers=headers,
                      params=params, data=data1)  # update policy
        NewPw = ''.join(random.sample(string.ascii_letters + string.digits, 8))
        data = '{"CurrentPw":"" , "NewPw":"' + NewPw + '","ResetPassword" : false}'
        requests.post(f"{embyurl}/emby/users/{r['Id']}/Password?api_key={embyapi}",
                      headers=headers, data=data)
        pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
        pd_user = pd_read_sql_query('SELECT * FROM user;')
        tgid_find = (pd_user['tgid'] == tgid)
        tgid_a = (pd_user[tgid_find]['tgid'])
        tgid_a = tgid_a.to_list()
        tgid_find = (pd_user['tgid'] == tgid)
        try:
            tgid_a = int(pd_user[tgid_find]['tgid'])  # find the tgid if the user is in the databse
        except TypeError:
            df_write = pd.DataFrame(
                {'tgid': tgid, 'admin': 'F', 'emby_name': str(r['Name']), 'emby_id': str(r['Id']), 'canrig': 'F'},
                index=[0])
            pd_to_sql(df_write, 'user', index=False, if_exists='append')  # add the user info
            return r['Name'], NewPw
        sqlemby_name = f"UPDATE `{db_name}`.`user` SET `emby_name`='{r['Name']}' WHERE `tgid`='{tgid}';"
        sqlcanrig = f"UPDATE `{db_name}`.`user` SET `canrig`='F' WHERE `tgid`={tgid};"
        sqlemby_id = f"UPDATE `{db_name}`.`user` SET `emby_id`='{r['Id']}' WHERE `tgid`='{tgid}';"
        db_execute(sqlcanrig)
        db_execute(sqlemby_name)
        db_execute(sqlemby_id)
        pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
        pd_user = pd_read_sql_query('SELECT * FROM user;')
        return r['Name'], NewPw
    else:
        write_config(config='register_method', params='None')
        write_config(config='register_public_time', params='0')
        return 'C'


async def create_user(message: Message):
    global pd_user
    global pd_invite_code
    tgid = message.from_user.id
    register_public_user = load_config('register_public_user')
    if register_public_user > 0:
        pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
        pd_user = pd_read_sql_query('SELECT * FROM user;')
        if hadname(message.from_user.id) == 'B':
            return 'A'  # already have an account
        message = str(message.text).split(' ')
        name = message[-1]
        if name == '' or name == ' ':
            return 'B'  # do not input a name
        data = '{"Name":"' + name + '","HasPassword":true}'
        params = (('api_key', embyapi),
                  )
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
        }
        r = requests.post(url=embyurl + '/emby/Users/New', headers=headers,
                          params=params, data=data).text
        try:
            r = json.loads(r)  # create a new user
        except json.decoder.JSONDecodeError:
            if r.find('already exists.'):
                return 'D'  # already exists
        data1 = '''{
            "IsAdministrator": false,
            "IsHidden": true,
            "IsHiddenRemotely": true,
            "IsDisabled": false,
            "EnableRemoteControlOfOtherUsers": false,
            "EnableSharedDeviceControl": false,
            "EnableRemoteAccess": true,
            "EnableLiveTvManagement": false,
            "EnableLiveTvAccess": true,
            "EnableMediaPlayback": true,
            "EnableAudioPlaybackTranscoding": false,
            "EnableVideoPlaybackTranscoding": false,
            "EnablePlaybackRemuxing": false,
            "EnableContentDeletion": false,
            "EnableContentDownloading": false,
            "EnableSubtitleDownloading": false,
            "EnableSubtitleManagement": false,
            "EnableSyncTranscoding": false,
            "EnableMediaConversion": false,
            "EnableAllDevices": true,
            "SimultaneousStreamLimit": 3
        }'''
        requests.post(embyurl + '/emby/Users/' + r['Id'] + '/Policy',
                      headers=headers,
                      params=params, data=data1)  # update policy
        NewPw = ''.join(random.sample(string.ascii_letters + string.digits, 8))
        data = '{"CurrentPw":"" , "NewPw":"' + NewPw + '","ResetPassword" : false}'
        requests.post(f"{embyurl}/emby/users/{r['Id']}/Password?api_key={embyapi}",
                      headers=headers, data=data)
        pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
        pd_user = pd_read_sql_query('SELECT * FROM user;')
        tgid_find = (pd_user['tgid'] == tgid)
        tgid_a = (pd_user[tgid_find]['tgid'])
        tgid_a = tgid_a.to_list()
        tgid_find = (pd_user['tgid'] == tgid)
        try:
            tgid_a = int(pd_user[tgid_find]['tgid'])  # find the tgid if the user is in the databse
        except TypeError:
            df_write = pd.DataFrame(
                {'tgid': tgid, 'admin': 'F', 'emby_name': str(r['Name']), 'emby_id': str(r['Id']), 'canrig': 'F'},
                index=[0])
            pd_to_sql(df_write, 'user', index=False, if_exists='append')  # add the user info
            write_config(config='register_public_user', params=register_public_user - 1)
            return r['Name'], NewPw
        sqlemby_name = f"UPDATE `{db_name}`.`user` SET `emby_name`='{r['Name']}' WHERE `tgid`='{tgid}';"
        sqlcanrig = f"UPDATE `{db_name}`.`user` SET `canrig`='F' WHERE `tgid`={tgid};"
        sqlemby_id = f"UPDATE `{db_name}`.`user` SET `emby_id`='{r['Id']}' WHERE `tgid`='{tgid}';"
        db_execute(sqlcanrig)
        db_execute(sqlemby_name)
        db_execute(sqlemby_id)
        pd_invite_code = pd_read_sql_query('SELECT * FROM invite_code;')
        pd_user = pd_read_sql_query('SELECT * FROM user;')
        write_config(config='register_public_user', params=register_public_user - 1)
        return r['Name'], NewPw
    else:
        write_config(config='register_method', params='None')
        write_config(config='register_public_user', params='0')
        return 'C'


def load_config(config: str):
    global pd_config
    pd_config = pd_read_sql_query('SELECT * FROM config;')
    result = pd_config.at[0, config]
    return result


def write_config(config='', params=''):
    code_used = f"UPDATE `{db_name}`.`config` SET `{config}`='{params}' WHERE `id`='1';"
    db_execute(code_used)
    return 'OK'


def ItemsCount():
    r = requests.get(f'{embyurl}/Items/Counts?api_key={embyapi}').text
    r = json.loads(r)
    MovieCount = r['MovieCount']
    SeriesCount = r['SeriesCount']
    EpisodeCount = r['EpisodeCount']
    return MovieCount, SeriesCount, EpisodeCount


async def refresh_group_members(groupids=[]):
    global tg_group_members
    global tg_group_administrators
    tg_group_members = {}
    if len(groupids) == 0:
        return

    for group_id in groupids:
        async for member in app.get_chat_members(group_id):
            if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                tg_group_administrators[member.user.id] = member.status
            if not member.user.is_restricted:
                tg_group_members[member.user.id] = member


async def refresh_channel_members(channelids=[]):
    global tg_channel_members
    tg_channel_members = {}
    if len(channelids) == 0:
        return

    for channel_id in channelids:
        async for member in app.get_chat_members(channel_id):
            if not member.user.is_restricted:
                tg_channel_members[member.user.id] = member


def allowed_commands(is_admin=False):
    common_commands = ['/invite', '/create', '/info', '/line', '/reset_emby_password', '/count', '/help']
    admin_commands = ['/library_refresh', '/new_code', '/register_all_time', '/register_all_user', '/info', '/ban_emby',
                      '/unban_emby']
    return common_commands if not is_admin else common_commands + admin_commands


####
## custom filters
####
async def filter_admin_func(_, __, message: Message):
    return IsAdmin(message.from_user.id)


async def filter_group_admin_func(_, __, message: Message):
    return IsGroupAdmin(message.from_user.id)

filter_admin = filters.create(filter_admin_func)
filter_group_admin = filters.create(filter_group_admin_func)


####
## left and join grouo message
####
@app.on_message(filters.left_chat_member | filters.new_chat_members)
async def my_handler(client: Client, message: Message):
    global tg_group_members
    if message.new_chat_members is not None and len(message.new_chat_members) > 0:
        for new_chat_member in message.new_chat_members:
            if new_chat_member \
                    and not new_chat_member.is_self \
                    and new_chat_member.id not in tg_group_members.keys():
                tg_group_members[new_chat_member.id] = new_chat_member
    if message.left_chat_member:
        if message.left_chat_member.id \
                and not message.left_chat_member.is_self \
                and message.left_chat_member.id in tg_group_members.keys():
            del tg_group_members[message.left_chat_member.id]


####
## group command
####
@app.on_message(filters.command('new_code') & filter_group_admin)
async def new_code_command(client: Client, message: Message):
    reply_from_user_id = ReplyToMessageFromUserId(message=message)
    if reply_from_user_id == 0:
        if prichat(message):
            result = await CreateCode(telegram_id=message.from_user.id)
            await message.reply(text=f'生成成功，邀请码\r\n<code>{result}</code>')
        else:
            total = 1
            if len(message.text.split(' ')) > 1:
                total = int(message.text.split(' ')[-1])
            for i in range(total):
                result = await CreateCode(telegram_id=message.from_user.id)
                await app.send_message(chat_id=message.chat.id, text=f'生成成功，邀请码\r\n<code>{result}</code>\r\n'
                                                                     f'如果已使用该邀请码请回复本条消息方便其他人')
    else:
        result = await CreateCode(telegram_id=message.from_user.id)
        await message.reply('已为这个用户生成邀请码')
        await app.send_message(chat_id=reply_from_user_id, text=f'生成成功，邀请码<code>{result}</code>')
        await app.send_message(
            chat_id=message.from_user.id,
            text=f'已为用户<a href="tg://user?id={reply_from_user_id}">{reply_from_user_id}</a>生成邀请码，邀请码<code>{result}</code>'
        )


@app.on_message(filters.command(['register_all_time']) & filter_admin)
async def register_all_time_command(client: Client, message: Message):
    result = await register_all_time(message)
    if result == 'A':
        await message.reply('您不是管理员，请勿随意使用管理命令')
    elif result == 'B':
        await message.reply('参数为空')
    else:
        expired = time.localtime(result)
        expired = time.strftime("%Y/%m/%d %H:%M:%S", expired)
        await message.reply(f"注册已开放，将在{expired}关闭注册")


@app.on_message(filters.command(['register_all_user']) & filter_admin)
async def register_all_user_command(client: Client, message: Message):
    result = await register_all_user(message)
    if result == 'A':
        await message.reply('您不是管理员，请勿随意使用管理命令')
    elif result == 'B':
        await message.reply('参数为空')
    else:
        await message.reply(f"注册已开放，本次共有{result}个名额")


@app.on_message(filters.command(['ban_emby']) & filter_group_admin)
async def ban_emby_command(client: Client, message: Message):
    reply_to_message_from_user_id = ReplyToMessageFromUserId(message)
    if reply_to_message_from_user_id > 0:
        result = await BanEmby(message, reply_to_message_from_user_id)
        if result[0] == 'A':
            await message.reply(
                f'用户<a href="tg://user?id={reply_to_message_from_user_id}">{reply_to_message_from_user_id}</a>的Emby账号{result[1]}已被ban')
            if ban_channel_id < -100:
                await app.send_message(
                    chat_id=ban_channel_id,
                    text=f'#Ban\n'
                         f'用户：<a href="tg://user?id={reply_to_message_from_user_id}">{reply_to_message_from_user_id}</a>\n'
                         f'Emby账号：{result[1]}\n'
                         f'原因：管理员封禁'
                )
        elif result[0] == 'B':
            await message.reply('请勿随意使用管理员命令')
        elif result[0] == 'C':
            await message.reply(
                f'用户<a href="tg://user?id={reply_to_message_from_user_id}">{reply_to_message_from_user_id}</a>没有Emby账号，但是已经取消了他的注册资格')
        elif result[0] == 'D':
            await message.reply(
                f'用户<a href="tg://user?id={reply_to_message_from_user_id}">{reply_to_message_from_user_id}</a>没有Emby账号，也没有注册资格')
    else:
        await message.reply('请回复一条消息使用该功能')


@app.on_message(filters.command(['unban_emby']) & filter_admin)
async def unban_emby_command(client: Client, message: Message):
    reply_to_message_from_user_id = ReplyToMessageFromUserId(message)
    if reply_to_message_from_user_id > 0:
        result = await UnbanEmby(message, reply_to_message_from_user_id)
        if result[0] == 'A':
            await message.reply(
                f'用户<a href="tg://user?id={reply_to_message_from_user_id}">{reply_to_message_from_user_id}</a>的Emby账号{result[1]}已解除封禁')
            if ban_channel_id < -100:
                await app.send_message(
                    chat_id=ban_channel_id,
                    text=f'#Unban\n'
                         f'用户：<a href="tg://user?id={reply_to_message_from_user_id}">{reply_to_message_from_user_id}</a>\n'
                         f'Emby账号：{result[1]}\n'
                         f'原因：管理员解封'
                )
        elif result[0] == 'B':
            await message.reply('请勿随意使用管理员命令')
        elif result[0] == 'C':
            await message.reply(
                f'用户<a href="tg://user?id={reply_to_message_from_user_id}">{reply_to_message_from_user_id}</a>没有Emby账号，也没有注册资格')
    else:
        await message.reply('请回复一条消息使用该命令')


####
## private message
####
@app.on_message(filters.private & filters.command(['create']))
async def create_command(client: Client, message: Message):
    if str(message.text) == "/create":
        await message.reply('请输入用户名，例如：/create embyplus')
        return
    register_method = load_config('register_method')
    result = 'C'
    if register_method == 'None':
        result = await create(message)
    elif register_method == 'User':
        result = await create_user(message)
    elif register_method == 'Time':
        result = await create_time(message)
    if result == 'A':
        await message.reply('您已经注册过emby账号，请勿重复注册')
    elif result == 'C':
        await message.reply('您还未获得注册资格')
    elif result == 'B':
        await message.reply('用户名非法')
    elif result == 'D':
        await message.reply('该用户名已被使用')
    else:
        await message.reply(
            f'创建成功，账号<code>{result[0]}</code>，初始密码为<code>{result[1]}</code>，密码不进行保存，请尽快登陆修改密码'
        )


@app.on_message(filters.command('invite') & filters.private)
async def invite_command(client: Client, message: Message):
    result = await invite(message)
    if result == 'A':
        await message.reply('没有找到这个邀请码')
    if result == 'B':
        await message.reply('邀请码已被使用')
    if result == 'C':
        await message.reply('已获得注册资格，邀请码已失效')
    if result == 'D':
        await message.reply('您已有账号或已经获得注册资格，请不要重复使用邀请码')


@app.on_message(filters.command('info'))
async def info_command(client: Client, message: Message):
    tgid = message.from_user.id
    reply_to_message_from_user_id = ReplyToMessageFromUserId(message)
    if reply_to_message_from_user_id > 0:
        result = userinfo(reply_to_message_from_user_id)
        if IsAdmin(tgid):
            if result == 'NotInTheDatabase':
                await message.reply('用户未入库，无信息')
            elif result[0] == 'HaveAnEmby':
                await message.reply('用户信息已私发，请查看')
                await app.send_message(chat_id=message.from_user.id,
                                       text=f'用户<a href="tg://user?id={reply_to_message_from_user_id}">{reply_to_message_from_user_id}</a>的信息\n'
                                            f'Emby Name: {result[1]}\n'
                                            f' Emby ID: {result[2]}\n'
                                            f'上次活动时间{result[3]}\n'
                                            f'账号创建时间{result[4]}\n'
                                            f'被ban时间{result[5]}')
            elif result[0] == 'NotHaveAnEmby':
                await message.reply(f'此用户没有emby账号，可注册：{result[1]}')
        else:
            await message.reply('非管理员请勿随意查看他人信息')
    else:
        result = userinfo(telegram_id=message.from_user.id)
        if result == 'NotInTheDatabase':
            await message.reply('用户未入库，无信息')
        elif result[0] == 'HaveAnEmby':
            await app.send_message(chat_id=message.from_user.id,
                                   text=f'用户<a href="tg://user?id={message.from_user.id}">{message.from_user.id}</a>的信息\n'
                                        f'Emby Name: {result[1]}\n'
                                        f' Emby ID: {result[2]}\n'
                                        f'上次活动时间{result[3]}\n'
                                        f'账号创建时间{result[4]}\n'
                                        f'被ban时间{result[5]}')
        elif result[0] == 'NotHaveAnEmby':
            await message.reply(f'此用户没有emby账号，可注册：{result[1]}')


@app.on_message(filters.command('library_refresh') & filter_admin)
async def library_refresh_command(client: Client, message: Message):
    requests.post(embyurl + '/Library/Refresh',
                  headers={
                      'accept': 'application/json',
                      'Content-Type': 'application/json',
                  },
                  params=(('api_key', embyapi),)
                  )


@app.on_message(filters.command(['help', 'start']))
async def help_command(client: Client, message: Message):
    help_message = '用户命令：\n' \
                   '/invite + 邀请码 使用邀请码获取创建账号资格\n' \
                   '/create + 用户名 创建用户（只允许英文、下划线，最低5位）\n' \
                   '/info 查看用户信息（仅可查看自己的信息）\n' \
                   '/line 查看线路\n' \
                   '/reset_emby_password 重置emby账号\n' \
                   '/count 查看服务器内片子数量\n' \
                   '/help 输出本帮助\n'
    if IsAdmin(message.from_user.id):
        help_message += '管理命令：\n' \
                        '/library_refresh 刷新媒体库 \n' \
                        '/new_code 创建新的邀请码 \n' \
                        '/register_all_time + 时间（分）开放注册，时长为指定时间\n' \
                        '/register_all_user + 人数 开放指定数量的注册名额\n' \
                        '/info 回复一位用户，查看他的信息\n' \
                        '/ban_emby 禁用一位用户的Emby账号\n' \
                        '/unban_emby 解禁一位用户的Emby账户'
    await message.reply(help_message)


@app.on_message(filters.command('line') & filters.private)
async def line_command(client: Client, message: Message):
    if hadname(message.from_user.id) == 'B':
        await message.reply(line, disable_web_page_preview=True)
    else:
        await message.reply('无Emby账号无法查看线路')


@app.on_message(filters.command('reset_emby_password') & filters.private)
async def reset_emby_password_command(client: Client, message: Message):
    if hadname(message.from_user.id) == 'B':
        pd_user = pd_read_sql_query('SELECT * FROM user;')
        tgid_find = (pd_user['tgid'] == message.from_user.id)
        emby_id = (pd_user[tgid_find]['emby_id'])
        emby_id = emby_id.to_list()
        emby_id = emby_id[-1]

        data = '{"ResetPassword" : true}'
        r = requests.post(f"{embyurl}/emby/users/{emby_id}/Password?api_key={embyapi}", headers={
            'accept': 'application/json',
            'Content-Type': 'application/json',
        }, data=data)

        newPw = ''.join(random.sample(string.ascii_letters + string.digits, 8))
        data = '{"CurrentPw":"" , "NewPw":"' + newPw + '","ResetPassword" : false}'
        r = requests.post(f"{embyurl}/emby/users/{emby_id}/Password?api_key={embyapi}", headers={
                      'accept': 'application/json',
                      'Content-Type': 'application/json',
                  }, data=data)
        await message.reply(
            f'重置成功，新密码为<code>{newPw}</code>，密码不进行保存，请尽快登陆修改密码'
        )
    else:
        await message.reply('无Emby账号')


@app.on_message(filters.command('count'))
async def count_command(client: Client, message: Message):
    result = ItemsCount()
    await message.reply(f'🎬电影数量：{result[0]}\n'
                        f'📽️剧集数量：{result[1]}\n'
                        f'🎞️总集数：{result[2]}')


@app.on_message(filters.command('求片'))
async def qiupian_command(client: Client, message: Message):
    text = str(message).split(' ')
    url = text[1]
    name = text[2]
    if url.find('imdb.com') == -1 or url.find('ref') != -1 or url.find('title') == -1:
        await message.reply('链接不符合规范')
    else:
        await message.reply('已发送请求')
        await app.send_message(
            chat_id=ban_channel_id,
            text=f'#求片\n'
                 f'影片名 #{name}\n'
                 f'IMDB链接：<code>{url}</code>\n'
                 f'TGID <a href="tg://user?id={message.from_user.id}">{message.from_user.id}</a>'
        )


@app.on_message(filters.text & filters.group)
async def diy_reply(client: Client, message: Message):
    reply_msg = {'6': ('sb', 'SB', '傻逼')}
    msg = str(message.text)
    if msg in reply_msg.keys():
        await message.reply(random.choice(reply_msg[msg]))


@app.on_message(filters.text & filters.private)
async def my_handler(client: Client, message: Message):
    tgid = message.from_user.id

    global tg_group_members
    global tg_channel_members
    is_in_channel = tg_group_members is not None and tgid in tg_group_members.keys()
    is_in_group = tg_channel_members is not None and tgid in tg_channel_members.keys()
    if not is_in_channel and not is_in_group:
        await message.reply(group_enter_message)
        return

    if not is_in_channel:
        await message.reply(channel_enter_message)


async def main():
    async with app:
        await refresh_group_members(groupid)
        await refresh_channel_members(channelid)
        await idle()


app.run(main())
