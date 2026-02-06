# This Python file uses the following encoding: utf-8
import subprocess
import tempfile
import lzma
import os
import time
import json
import random

import requests
import urllib3

from tasks.base_task import BaseTask
from module.logger import logger
from module.exception import TaskEnd

urllib3.disable_warnings()
os.environ['MSYS_NO_PATHCONV'] = '1'

WELFARE_BASE = "https://god-welfare.gameyw.netease.com"
GL_PACKAGE = "com.netease.gl"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FRIDA_SERVER_LOCAL = os.path.join(SCRIPT_DIR, "frida-server-17.6.2-android-x86_64")
FRIDA_SERVER_XZ = FRIDA_SERVER_LOCAL + ".xz"
FRIDA_SERVER_REMOTE = "/data/local/tmp/frida-server"
ADB_PATH = os.path.join(SCRIPT_DIR, "platform-tools", "adb.exe")

APP_KEY = "g37"
GL_VERSION = "4.11.0"
GL_CLIENTTYPE = "50"


class ScriptTask(BaseTask):

    def run(self):
        self.gl_uid = ""
        self.gl_token = ""
        self.gl_deviceid = ""
        self.gl_source = "URS"
        self.role_id = ""
        self.server = ""
        self.app_key = APP_KEY
        self.frida_pid = None

        self.session = requests.Session()
        self.session.verify = False

        logger.hr('AutoCheckinBigGod', level=1)

        # [1/5] 检查运行环境
        logger.info('[1/5] 检查运行环境...')
        if not self._check_adb_connection():
            logger.error('未检测到ADB设备，请确保模拟器已启动并已连接ADB')
            self.set_next_run('AutoCheckinBigGod', success=False, finish=True)
            raise TaskEnd('AutoCheckinBigGod')
        logger.info('ADB已连接')

        if not self._ensure_frida_server_running():
            logger.error('Frida Server启动失败，请检查模拟器环境')
            self.set_next_run('AutoCheckinBigGod', success=False, finish=True)
            raise TaskEnd('AutoCheckinBigGod')
        logger.info('Frida Server运行中')

        # [2/5] 启动大神APP
        logger.info('[2/5] 启动大神APP...')
        pid = self._launch_app()
        if not pid:
            logger.error('无法启动大神APP，请确保模拟器中已安装大神APP')
            self.set_next_run('AutoCheckinBigGod', success=False, finish=True)
            raise TaskEnd('AutoCheckinBigGod')
        self.frida_pid = pid
        logger.info(f'大神APP已运行 (PID: {pid})')

        # [3/5] 获取Token
        logger.info('[3/5] 获取Token...')
        token_data = None
        for attempt in range(1, 4):
            token_data = self._extract_token(pid)
            if token_data:
                break
            if attempt < 3:
                logger.warning(f'第{attempt}次获取Token失败，等待{10 * attempt}秒后重试...')
                time.sleep(10 * attempt)
                new_pid = self._get_app_pid()
                if new_pid:
                    pid = new_pid
                    self.frida_pid = pid
        if not token_data:
            logger.error('无法获取Token，请确保已登录大神APP')
            self.set_next_run('AutoCheckinBigGod', success=False, finish=True)
            raise TaskEnd('AutoCheckinBigGod')

        self.gl_uid = token_data.get('GL_UID', '')
        self.gl_token = token_data.get('GL_TOKEN', '')
        self.gl_deviceid = token_data.get('GL_DEVICEID', '')
        self.gl_source = token_data.get('GL_SOURCE', 'URS')
        self.role_id = token_data.get('ROLE_ID', '')
        self.server = token_data.get('SERVER', '')
        if token_data.get('APP_KEY'):
            self.app_key = token_data.get('APP_KEY')
        logger.info(f'Token获取成功! 用户ID: {self.gl_uid[:16]}...')

        # Token已获取，将大神APP切到后台，减少对用户的干扰
        try:
            self._adb_shell(['input', 'keyevent', 'KEYCODE_HOME'])
        except Exception:
            pass

        if self.role_id and self.server:
            logger.info(f'角色信息: {self.role_id} @ {self.server}')
        else:
            logger.warning('未能获取角色信息，请确保已在大神APP中绑定阴阳师角色')

        # [4/5] 获取礼包列表
        logger.info('[4/5] 获取礼包列表...')
        rewards = self._get_rewards()

        if not rewards:
            logger.info('没有可领取的礼包')
            self._cleanup()
            self.set_next_run('AutoCheckinBigGod', success=True, finish=True)
            raise TaskEnd('AutoCheckinBigGod')

        # [5/5] 领取礼包
        logger.info(f'[5/5] 领取 {len(rewards)} 个礼包...')
        success_count = 0
        for r in rewards:
            if self._claim_reward(r['id'], r['title']):
                success_count += 1
            time.sleep(1)

        logger.info(f'完成! 成功领取 {success_count}/{len(rewards)} 个礼包')
        self._cleanup()
        self.set_next_run('AutoCheckinBigGod', success=True, finish=True)
        raise TaskEnd('AutoCheckinBigGod')

    # ======================== 清理 ========================

    def _cleanup(self):
        logger.info('清理：关闭大神APP和Frida Server...')
        try:
            self._adb_shell(['am', 'force-stop', GL_PACKAGE])
        except Exception:
            pass
        try:
            self._adb_shell(['killall', 'frida-server'])
        except Exception:
            pass

    # ======================== ADB 操作 ========================

    def _adb_cmd(self, args, timeout=10):
        cmd = [ADB_PATH] + args
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()

    def _adb_shell(self, cmd, timeout=15):
        return self._adb_cmd(['shell'] + cmd, timeout=timeout)

    def _get_app_pid(self):
        try:
            output = self._adb_shell(['pidof', GL_PACKAGE])
            if output:
                return int(output.split()[0])
        except Exception as e:
            logger.warning(f'获取PID失败: {e}')
        return None

    def _launch_app(self):
        try:
            self._adb_shell(['am', 'force-stop', GL_PACKAGE])
            time.sleep(2)
            self._adb_shell([
                'monkey', '-p', GL_PACKAGE,
                '-c', 'android.intent.category.LAUNCHER', '1'
            ])
            logger.info('等待大神APP启动...')
            time.sleep(15)
            return self._get_app_pid()
        except Exception as e:
            logger.warning(f'启动APP失败: {e}')
            return None

    # ======================== Frida Server 管理 ========================

    def _check_adb_connection(self):
        try:
            output = self._adb_cmd(['devices'])
            lines = [l for l in output.strip().split('\n')[1:] if l.strip() and 'device' in l]
            return len(lines) > 0
        except Exception:
            return False

    def _is_frida_server_running(self):
        try:
            output = self._adb_shell(['ps | grep frida-server'])
            return 'frida-server' in output
        except Exception:
            return False

    def _is_frida_server_installed(self):
        try:
            output = self._adb_shell(['ls', '-l', FRIDA_SERVER_REMOTE])
            return 'No such file' not in output and FRIDA_SERVER_REMOTE in output
        except Exception:
            return False

    def _ensure_frida_local(self):
        if os.path.exists(FRIDA_SERVER_LOCAL):
            return True
        if not os.path.exists(FRIDA_SERVER_XZ):
            logger.error(f'找不到Frida Server压缩文件: {FRIDA_SERVER_XZ}')
            return False
        logger.info('解压Frida Server...')
        try:
            with lzma.open(FRIDA_SERVER_XZ, 'rb') as f_in:
                with open(FRIDA_SERVER_LOCAL, 'wb') as f_out:
                    f_out.write(f_in.read())
            logger.info('Frida Server解压完成')
            return True
        except Exception as e:
            logger.error(f'解压失败: {e}')
            return False

    def _push_frida_server(self):
        if not self._ensure_frida_local():
            return False
        logger.info('推送Frida Server到模拟器...')
        try:
            self._adb_cmd(['push', FRIDA_SERVER_LOCAL, FRIDA_SERVER_REMOTE], timeout=30)
            self._adb_shell(['chmod', '755', FRIDA_SERVER_REMOTE])
            logger.info('Frida Server推送完成')
            return True
        except Exception as e:
            logger.error(f'推送失败: {e}')
            return False

    def _start_frida_server(self):
        logger.info('启动Frida Server...')
        subprocess.Popen(
            [ADB_PATH, 'shell', f'{FRIDA_SERVER_REMOTE} &'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(3)
        if self._is_frida_server_running():
            logger.info('Frida Server已启动')
            return True
        logger.error('Frida Server启动失败，请确保模拟器已开启Root模式')
        return False

    def _ensure_frida_server_running(self):
        if self._is_frida_server_running():
            return True
        if not self._is_frida_server_installed():
            if not self._push_frida_server():
                return False
        return self._start_frida_server()

    # ======================== Frida 脚本执行 ========================

    def _run_frida_script(self, pid, script_content, wait_time=3, timeout=10):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(script_content)
            script_path = f.name
        try:
            process = subprocess.Popen(
                ['frida', '-U', '-p', str(pid), '-l', script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            time.sleep(wait_time)
            stdout, stderr = process.communicate(input='exit\n', timeout=timeout)
            return stdout + stderr
        except subprocess.TimeoutExpired:
            process.kill()
            logger.warning('Frida脚本执行超时')
            return None
        except Exception as e:
            logger.warning(f'Frida脚本执行失败: {e}')
            return None
        finally:
            try:
                os.unlink(script_path)
            except:
                pass

    def _extract_token(self, pid):
        script = f"""
Java.perform(function() {{
    Java.choose('com.netease.gl.serviceaccount.proto.auth.GLAuth$Authed', {{
        onMatch: function(instance) {{
            var uid = instance.getUid();
            var token = instance.getToken();
            var source = instance.getSource();
            if (uid && token) {{
                console.log('GL_UID:' + uid);
                console.log('GL_TOKEN:' + token);
                console.log('GL_SOURCE:' + source);
            }}
        }},
        onComplete: function() {{}}
    }});

    try {{
        var YXFDeviceInfo = Java.use('com.netease.gl.glbase.build.YXFDeviceInfo');
        console.log('GL_DEVICEID:' + YXFDeviceInfo.getDeviceId());
    }} catch(e) {{}}

    Java.choose('com.netease.gl.serviceim.entity.chatroom.GameRoleCardEntity', {{
        onMatch: function(instance) {{
            var appKey = instance.getAppKey ? instance.getAppKey() : null;
            if (appKey === '{self.app_key}') {{
                var displayInfos = instance.getRoleCardDisplayInfos();
                if (displayInfos && displayInfos.size() > 0) {{
                    var info = displayInfos.get(0);
                    var fields = info.getClass().getDeclaredFields();
                    for (var i = 0; i < fields.length; i++) {{
                        fields[i].setAccessible(true);
                        var name = fields[i].getName();
                        try {{
                            var value = fields[i].get(info);
                            if (name === 'roleId' && value) {{
                                console.log('ROLE_ID:' + value);
                            }} else if (name === 'server' && value) {{
                                console.log('SERVER:' + value);
                            }}
                        }} catch(e) {{}}
                    }}
                    console.log('APP_KEY:' + appKey);
                }}
            }}
        }},
        onComplete: function() {{}}
    }});
}});
"""
        output = self._run_frida_script(pid, script, wait_time=3, timeout=10)
        if not output:
            return None

        data = {}
        for line in output.split('\n'):
            if 'GL_UID:' in line:
                data['GL_UID'] = line.split('GL_UID:')[1].strip()
            elif 'GL_TOKEN:' in line and 'GL_TOKEN' not in data:
                data['GL_TOKEN'] = line.split('GL_TOKEN:')[1].strip()
            elif 'GL_DEVICEID:' in line:
                data['GL_DEVICEID'] = line.split('GL_DEVICEID:')[1].strip()
            elif 'GL_SOURCE:' in line:
                data['GL_SOURCE'] = line.split('GL_SOURCE:')[1].strip()
            elif 'ROLE_ID:' in line:
                data['ROLE_ID'] = line.split('ROLE_ID:')[1].strip()
            elif 'SERVER:' in line:
                data['SERVER'] = line.split('SERVER:')[1].strip()
            elif 'APP_KEY:' in line:
                data['APP_KEY'] = line.split('APP_KEY:')[1].strip()

        if data.get('GL_UID') and data.get('GL_TOKEN'):
            return data
        return None

    def _frida_sign(self, url, body, headers=None):
        if not self.frida_pid:
            self.frida_pid = self._get_app_pid()
        if not self.frida_pid:
            logger.error('无法获取APP PID，请确保大神APP已打开')
            return None

        headers_code = ""
        if headers:
            for k, v in headers.items():
                v = v.replace("'", "\\'")
                headers_code += f"map.put('{k}', '{v}');\n"

        body_escaped = body.replace("\\", "\\\\").replace("'", "\\'")

        script = f"""
Java.perform(function() {{
    var Tools = Java.use('com.netease.nep.Tools');
    var HashMap = Java.use('java.util.HashMap');
    var map = HashMap.$new();
    {headers_code}
    var result = Tools.getPostMethodSignatures('{url}', '{body_escaped}', map);
    console.log('SIGNED_URL:' + result);
}});
"""
        output = self._run_frida_script(self.frida_pid, script, wait_time=2, timeout=15)
        if not output:
            return None

        for line in output.split('\n'):
            if 'SIGNED_URL:' in line:
                return line.split('SIGNED_URL:')[1].strip()
        return None

    # ======================== HTTP API ========================

    def _generate_nonce(self):
        return str(random.randint(-9000000000000000000, 9000000000000000000))

    def _build_headers(self, nonce=None):
        if not nonce:
            nonce = self._generate_nonce()
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"Mozilla/5.0 (Linux; Android 12) Godlike/{GL_VERSION}",
            "gl-version": GL_VERSION,
            "gl-source": self.gl_source,
            "gl-deviceid": self.gl_deviceid,
            "gl-token": self.gl_token,
            "gl-clienttype": GL_CLIENTTYPE,
            "gl-uid": self.gl_uid,
            "gl-nonce": nonce,
            "Origin": "https://act.ds.163.com",
            "Referer": "https://act.ds.163.com/",
        }

    def _get_rewards(self):
        url = f"{WELFARE_BASE}/v1/welfare/getAppInfos"
        payload = {
            "appKey": self.app_key,
            "roleId": self.role_id,
            "server": self.server,
        }
        try:
            resp = self.session.post(url, json=payload, headers=self._build_headers(), timeout=15)
            data = resp.json()

            if data.get('code') != 200:
                logger.warning(f'获取礼包失败: {data.get("errmsg")}')
                return []

            rewards = []
            for app_info in data.get('result', []):
                for bag in app_info.get('rewardBags', []):
                    bag_id = bag.get('id')
                    title = bag.get('title', '')
                    completed = bag.get('completed', False)
                    has_apply = bag.get('hasApplay', False)
                    desc = bag.get('fixedRewardDesc', '')

                    if has_apply:
                        logger.info(f'  [已领取] {title}')
                    elif completed:
                        logger.info(f'  [可领取] {title} - {desc}')
                        rewards.append({'id': bag_id, 'title': title})
                    else:
                        logger.info(f'  [未完成] {title}')

            return rewards

        except Exception as e:
            logger.error(f'获取礼包请求异常: {e}')
            return []

    def _claim_reward(self, bag_id, title):
        base_url = f"{WELFARE_BASE}/v1/welfare/applyRewardV2"
        payload = {
            "appKey": self.app_key,
            "rewardBagId": bag_id,
            "roleId": self.role_id,
            "server": self.server,
        }

        nonce = self._generate_nonce()
        sign_headers = {
            "GL-ClientType": GL_CLIENTTYPE,
            "GL-DeviceId": self.gl_deviceid,
            "GL-Nonce": nonce,
            "GL-Token": self.gl_token,
            "GL-Uid": self.gl_uid,
        }

        logger.info(f'  正在领取: {title}...')
        signed_url = self._frida_sign(base_url, json.dumps(payload), sign_headers)

        if not signed_url:
            logger.warning(f'  签名失败: {title}')
            return False

        try:
            headers = self._build_headers(nonce)
            resp = self.session.post(signed_url, json=payload, headers=headers, timeout=15)
            data = resp.json()

            code = data.get('code')
            msg = data.get('errmsg', '')

            if code == 200:
                logger.info(f'  领取成功: {title}')
                return True
            elif code == 801 or '已领取' in msg:
                logger.info(f'  已领取过: {title}')
            else:
                logger.warning(f'  领取失败: {title} - {msg}')

        except Exception as e:
            logger.error(f'  领取异常: {title} - {e}')

        return False
