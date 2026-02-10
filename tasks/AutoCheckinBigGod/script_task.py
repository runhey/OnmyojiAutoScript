# This Python file uses the following encoding: utf-8
import subprocess
import tempfile
import lzma
import os
import sys
import time
import json
import random

# 直接运行本脚本时，需要先将项目根目录加入 Python 路径
if __name__ == '__main__' and 'tasks' not in sys.modules:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

import requests
import urllib3

from tasks.base_task import BaseTask
from module.logger import logger
from module.exception import TaskEnd

urllib3.disable_warnings()
os.environ['MSYS_NO_PATHCONV'] = '1'

WELFARE_BASE = "https://god-welfare.gameyw.netease.com"
LOGIN_BASE = "https://god.gameyw.netease.com"
GL_PACKAGE = "com.netease.gl"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FRIDA_SERVER_LOCAL = os.path.join(SCRIPT_DIR, "frida-server-17.6.2-android-x86_64")
FRIDA_SERVER_XZ = FRIDA_SERVER_LOCAL + ".xz"
FRIDA_SERVER_REMOTE = "/data/local/tmp/frida-server"
ADB_PATH = os.path.join(SCRIPT_DIR, "platform-tools", "adb.exe")

# 获取项目 Python 路径（当前运行的 Python）
PYTHON_PATH = sys.executable

APP_KEY = "g37"
GL_VERSION = "4.12.0"  # 默认值，运行时会从APP动态获取
GL_CLIENTTYPE = "50"


class ScriptTask(BaseTask):

    def run(self):
        self.gl_uid = ""
        self.gl_token = ""
        self.gl_deviceid = ""
        self.gl_source = "URS"
        self.gl_version = GL_VERSION
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
        token_data = self._try_extract_token(pid)

        # 如果内存提取失败，通过 auth 数据库 + HTTP API 自动登录
        if not token_data:
            logger.warning('内存中未找到Token，尝试通过URS凭据自动登录...')
            new_pid, login_token = self._auto_login(pid)
            if new_pid:
                pid = new_pid
                self.frida_pid = pid
            if login_token:
                token_data = login_token

        if not token_data:
            logger.error('无法获取Token，请确保已登录大神APP并绑定阴阳师角色')
            self.set_next_run('AutoCheckinBigGod', success=False, finish=True)
            raise TaskEnd('AutoCheckinBigGod')

        self.gl_uid = token_data.get('GL_UID', '')
        self.gl_token = token_data.get('GL_TOKEN', '')
        self.gl_deviceid = token_data.get('GL_DEVICEID', '')
        self.gl_source = token_data.get('GL_SOURCE', 'URS')
        if token_data.get('GL_VERSION'):
            self.gl_version = token_data['GL_VERSION']
            logger.info(f'APP版本: {self.gl_version}')
        logger.info(f'Token获取成功! 用户ID: {self.gl_uid[:16]}...')

        # Token已获取，将大神APP切到后台，减少对用户的干扰
        try:
            self._adb_shell(['input', 'keyevent', 'KEYCODE_HOME'])
        except Exception:
            pass

        # 通过API获取角色信息
        logger.info('通过API获取角色信息...')
        role_info = self._get_role_info()
        if role_info:
            self.role_id = role_info.get('roleId', '')
            self.server = role_info.get('server', '')
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
            self._adb_shell(['su', '-c', 'killall frida-server'])
        except Exception:
            pass

    # ======================== ADB 操作 ========================

    def _adb_cmd(self, args, timeout=10):
        # 如果有设备序列号且命令不是 connect/devices，则添加 -s 参数指定设备
        cmd = [ADB_PATH]
        if hasattr(self, '_adb_serial') and self._adb_serial and args[0] not in ['connect', 'devices']:
            cmd.extend(['-s', self._adb_serial])
        cmd.extend(args)
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
        """启动大神APP。如果已在运行则直接返回PID，不会force-stop。"""
        try:
            # 先检查是否已在运行
            pid = self._get_app_pid()
            if pid:
                logger.info('大神APP已在运行，无需重启')
                return pid

            # APP未运行，启动它
            self._adb_shell([
                'monkey', '-p', GL_PACKAGE,
                '-c', 'android.intent.category.LAUNCHER', '1'
            ])
            logger.info('等待大神APP启动...')
            for _ in range(15):
                time.sleep(2)
                pid = self._get_app_pid()
                if pid:
                    return pid
            return None
        except Exception as e:
            logger.warning(f'启动APP失败: {e}')
            return None

    # ======================== Frida Server 管理 ========================

    def _check_adb_connection(self):
        try:
            serial = str(self.config.script.device.serial)
            if serial and serial != 'auto':
                logger.info(f'专用ADB连接到 {serial}...')
                result = self._adb_cmd(['connect', serial], timeout=10)
                if 'connected' not in result.lower() and 'already connected' not in result.lower():
                    logger.warning(f'ADB连接失败: {result}')
                    return False
                # 保存设备序列号，用于后续命令指定设备
                # adb connect 不带端口时会自动补 :5555，需要从 devices 列表中获取实际名称
                # 因为 Frida -D 参数需要精确匹配 adb devices 中的设备名
                self._adb_serial = serial
            else:
                self._adb_serial = None

            output = self._adb_cmd(['devices'])
            lines = [l for l in output.strip().split('\n')[1:] if l.strip() and '\tdevice' in l]

            if len(lines) == 0:
                logger.warning('未检测到任何设备')
                return False

            # 从 adb devices 输出中获取实际的设备 serial（可能带端口号）
            # 例如用户配置 192.168.1.66，adb devices 中显示 192.168.1.66:5555
            if self._adb_serial:
                for l in lines:
                    actual_serial = l.split('\t')[0].strip()
                    if actual_serial.startswith(self._adb_serial):
                        if actual_serial != self._adb_serial:
                            logger.info(f'设备实际名称: {actual_serial}')
                        self._adb_serial = actual_serial
                        break

            # 如果没有指定 serial 且只有一个设备，自动使用该设备
            if not self._adb_serial and len(lines) == 1:
                device_line = lines[0].split('\t')[0]
                self._adb_serial = device_line.strip()
                logger.info(f'自动使用设备: {self._adb_serial}')

            return True
        except Exception as e:
            logger.warning(f'ADB连接检查失败: {e}')
            return False

    def _is_frida_server_running(self):
        try:
            output = self._adb_shell(['ps | grep frida-server'])
            if 'frida-server' not in output:
                return False
            # 确保是以 root 身份运行，否则无法 attach 进程
            for line in output.strip().split('\n'):
                if 'frida-server' in line and 'grep' not in line:
                    if line.strip().startswith('root'):
                        return True
            # frida-server 存在但不是 root 运行，杀掉重启
            logger.warning('Frida Server未以root运行，正在重启...')
            try:
                self._adb_shell(['killall', 'frida-server'])
            except Exception:
                pass
            return False
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
            # 先删除旧文件（如果存在）
            try:
                self._adb_shell(['rm', '-f', FRIDA_SERVER_REMOTE])
            except:
                pass

            # 推送文件
            self._adb_cmd(['push', FRIDA_SERVER_LOCAL, FRIDA_SERVER_REMOTE], timeout=60)

            # 验证推送是否成功（检查文件大小）
            local_size = os.path.getsize(FRIDA_SERVER_LOCAL)
            remote_check = self._adb_shell(['ls', '-l', FRIDA_SERVER_REMOTE])

            if 'No such file' in remote_check:
                logger.error('推送失败: 文件未找到')
                return False

            # 从 ls -l 输出提取文件大小（格式如：-rwxr-xr-x 1 root root 105123456 ...）
            try:
                parts = remote_check.split()
                if len(parts) >= 5:
                    remote_size = int(parts[4])
                    if remote_size != local_size:
                        logger.error(f'推送失败: 文件大小不匹配 (本地: {local_size}, 远程: {remote_size})')
                        return False
            except:
                pass

            self._adb_shell(['chmod', '755', FRIDA_SERVER_REMOTE])
            logger.info('Frida Server推送完成')
            return True
        except subprocess.TimeoutExpired:
            logger.error('推送超时，请检查网络连接和模拟器状态')
            return False
        except Exception as e:
            logger.error(f'推送失败: {e}')
            return False

    def _start_frida_server(self):
        logger.info('启动Frida Server...')
        # 使用 su + nohup 以 root 身份后台启动，否则无权 attach 其他进程
        # 将 stdout/stderr 重定向到 /dev/null 避免阻塞
        start_cmd = f'su -c "nohup {FRIDA_SERVER_REMOTE} > /dev/null 2>&1 &"'
        try:
            self._adb_shell([start_cmd], timeout=5)
        except subprocess.TimeoutExpired:
            # su 启动可能超时，但进程已经在后台运行了
            pass
        except Exception:
            pass
        # 轮询检测启动状态，最多等10秒
        for _ in range(5):
            time.sleep(2)
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
            # 获取 frida 可执行文件路径
            # frida-tools 安装后会在 Python Scripts 目录下生成 frida.exe
            python_dir = os.path.dirname(PYTHON_PATH)
            frida_exe = os.path.join(python_dir, 'Scripts', 'frida.exe')

            # 如果找不到 frida.exe，尝试直接使用 frida 命令（依赖 PATH）
            if not os.path.exists(frida_exe):
                frida_exe = 'frida'

            # 构建 frida 命令
            if hasattr(self, '_adb_serial') and self._adb_serial:
                frida_cmd = [frida_exe, '-D', self._adb_serial, '-p', str(pid), '-l', script_path]
            else:
                frida_cmd = [frida_exe, '-U', '-p', str(pid), '-l', script_path]

            process = subprocess.Popen(
                frida_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # 等待脚本执行完成
            time.sleep(wait_time)

            # 关闭 stdin 触发 frida 退出，然后读取输出
            process.stdin.close()
            try:
                stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout_bytes, stderr_bytes = process.communicate()

            # 使用 utf-8 解码，忽略无法解码的字符
            stdout = stdout_bytes.decode('utf-8', errors='ignore') if stdout_bytes else ''
            stderr = stderr_bytes.decode('utf-8', errors='ignore') if stderr_bytes else ''
            output = stdout + stderr

            return output
        except Exception as e:
            logger.warning(f'Frida脚本执行失败: {e}')
            return None
        finally:
            try:
                os.unlink(script_path)
            except:
                pass

    def _try_extract_token(self, pid):
        """尝试多次从内存提取 Token（GL_UID/GL_TOKEN/GL_DEVICEID），返回 dict 或 None。"""
        for attempt in range(1, 4):
            token_data = self._extract_token(pid)
            if token_data:
                return token_data
            logger.warning(f'第{attempt}次获取Token失败，等待5秒后重试...')
            if attempt < 3:
                time.sleep(5)
                new_pid = self._get_app_pid()
                if new_pid:
                    pid = new_pid
                    self.frida_pid = pid
        return None

    def _extract_token(self, pid):
        """通过 Frida 从内存中提取 GL 认证信息（UID/Token/DeviceId/Source）"""
        script = """
Java.perform(function() {
    Java.choose('com.netease.gl.serviceaccount.proto.auth.GLAuth$Authed', {
        onMatch: function(instance) {
            var uid = instance.getUid();
            var token = instance.getToken();
            var source = instance.getSource();
            if (uid && token) {
                console.log('GL_UID:' + uid);
                console.log('GL_TOKEN:' + token);
                console.log('GL_SOURCE:' + source);
            }
        },
        onComplete: function() {}
    });

    try {
        var YXFDeviceInfo = Java.use('com.netease.gl.glbase.build.YXFDeviceInfo');
        console.log('GL_DEVICEID:' + YXFDeviceInfo.getDeviceId());
    } catch(e) {}

    // 获取APP版本号
    try {
        var AppProfile = Java.use('com.netease.gl.glbase.app.AppProfile');
        var ctx = AppProfile.getContext();
        var pm = ctx.getPackageManager();
        var pi = pm.getPackageInfo('com.netease.gl', 0);
        console.log('GL_VERSION:' + pi.versionName.value);
    } catch(e) {}
});
"""
        output = self._run_frida_script(pid, script, wait_time=5, timeout=15)
        if not output:
            logger.warning('Frida脚本无输出')
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
            elif 'GL_VERSION:' in line:
                data['GL_VERSION'] = line.split('GL_VERSION:')[1].strip()

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

    # ======================== 自动登录（读取auth数据库 + HTTP API） ========================

    def _auto_login(self, pid):
        """
        自动登录流程：
        1. 通过 Frida 读取 APP 的 auth SQLite 数据库，获取缓存的 URS 凭据
        2. 使用 URS 凭据调用 login-by-urs-token API 获取新的 GL Token
        前提：用户至少手动登录过一次（数据库中有缓存账号）。
        返回 (pid, token_data) 元组。token_data 为 dict 或 None。
        """
        # 第1步：从 auth 数据库读取 URS 凭据
        logger.info('从APP数据库读取URS凭据...')
        urs_creds = self._get_urs_credentials(pid)
        if not urs_creds:
            logger.error('无法读取URS凭据，请确保已手动登录过大神APP')
            return pid, None

        logger.info(f'获取到URS凭据，账号: {urs_creds.get("AUTH_ACCOUNT", "unknown")}')
        if urs_creds.get('GL_VERSION'):
            self.gl_version = urs_creds['GL_VERSION']
            logger.info(f'APP版本: {self.gl_version}')

        # 第2步：调用 login-by-urs-token API
        logger.info('调用登录API...')
        token_data = self._login_by_urs_token(pid, urs_creds)
        if token_data:
            logger.info('自动登录成功!')
            return self._get_app_pid(), token_data

        logger.warning('登录API调用失败')
        return self._get_app_pid(), None

    def _get_urs_credentials(self, pid):
        """通过 Frida 从 APP 的 auth SQLite 数据库中读取 URS 凭据"""
        script = """
Java.perform(function() {
    // 从 auth 数据库读取 userauths 表
    try {
        var AppProfile = Java.use('com.netease.gl.glbase.app.AppProfile');
        var ctx = AppProfile.getContext();
        var dbPath = ctx.getDatabasePath('auth');
        if (dbPath.exists()) {
            var SQLiteDatabase = Java.use('android.database.sqlite.SQLiteDatabase');
            var db = SQLiteDatabase.openDatabase(dbPath.getAbsolutePath(), null, 1);
            var cursor = db.rawQuery(
                "SELECT uid, token, account, ursAuthedToken, ursAuhtedId, authType FROM userauths LIMIT 1",
                null
            );
            if (cursor.moveToFirst()) {
                console.log('AUTH_UID:' + cursor.getString(0));
                console.log('AUTH_TOKEN:' + cursor.getString(1));
                console.log('AUTH_ACCOUNT:' + cursor.getString(2));
                console.log('AUTH_URS_TOKEN:' + cursor.getString(3));
                console.log('AUTH_URS_ID:' + cursor.getString(4));
                console.log('AUTH_TYPE:' + cursor.getString(5));
            }
            cursor.close();
            db.close();
        } else {
            console.log('AUTH_DB_ERROR:数据库文件不存在');
        }
    } catch(e) {
        console.log('AUTH_DB_ERROR:' + e);
    }

    // 获取 DeviceId
    try {
        var YXFDeviceInfo = Java.use('com.netease.gl.glbase.build.YXFDeviceInfo');
        console.log('GL_DEVICEID:' + YXFDeviceInfo.getDeviceId());
    } catch(e) {}

    // 获取 UDID
    try {
        var Settings = Java.use('android.provider.Settings$Secure');
        var AppProfile = Java.use('com.netease.gl.glbase.app.AppProfile');
        var ctx = AppProfile.getContext();
        var udid = Settings.getString(ctx.getContentResolver(), 'android_id');
        console.log('UDID:' + udid);
    } catch(e) {}

    // 获取APP版本号
    try {
        var AppProfile = Java.use('com.netease.gl.glbase.app.AppProfile');
        var ctx = AppProfile.getContext();
        var pm = ctx.getPackageManager();
        var pi = pm.getPackageInfo('com.netease.gl', 0);
        console.log('GL_VERSION:' + pi.versionName.value);
    } catch(e) {}
});
"""
        output = self._run_frida_script(pid, script, wait_time=5, timeout=15)
        if not output:
            return None

        data = {}
        for line in output.split('\n'):
            for key in ['AUTH_UID', 'AUTH_TOKEN', 'AUTH_ACCOUNT', 'AUTH_URS_TOKEN',
                        'AUTH_URS_ID', 'AUTH_TYPE', 'GL_DEVICEID', 'UDID', 'GL_VERSION']:
                tag = key + ':'
                if tag in line:
                    data[key] = line.split(tag)[1].strip()
            if 'AUTH_DB_ERROR:' in line:
                logger.warning(f'读取数据库失败: {line.split("AUTH_DB_ERROR:")[1].strip()}')

        if data.get('AUTH_URS_TOKEN') and data.get('AUTH_URS_ID'):
            return data

        logger.warning('数据库中无有效的URS凭据')
        return None

    def _login_by_urs_token(self, pid, urs_creds):
        """使用 URS 凭据调用 login-by-urs-token API 获取新的 GL Token"""
        base_url = f"{LOGIN_BASE}/v1/app/base/user/login-by-urs-token"
        device_id = urs_creds.get('GL_DEVICEID', '')
        udid = urs_creds.get('UDID', '')

        payload = {
            "urs": {
                "id": urs_creds['AUTH_URS_ID'],
                "token": urs_creds['AUTH_URS_TOKEN'],
                "type": int(urs_creds.get('AUTH_TYPE', '30'))
            },
            "account": urs_creds['AUTH_ACCOUNT'],
            "clientType": int(GL_CLIENTTYPE),
            "deviceId": device_id,
            "os": "android",
            "version": self.gl_version,
            "osVersion": "12",
            "device": "SDY-AN00",
            "udid": udid,
            "unisdkDeviceId": udid,
            "autoLogin": False
        }

        body_str = json.dumps(payload)
        nonce = self._generate_nonce()
        sign_headers = {
            "GL-ClientType": GL_CLIENTTYPE,
            "GL-DeviceId": device_id,
            "GL-Nonce": nonce,
        }

        # 需要 Frida 签名
        self.frida_pid = pid
        signed_url = self._frida_sign(base_url, body_str, sign_headers)
        if not signed_url:
            logger.warning('登录请求签名失败')
            return None

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "okhttp/4.9.1",
            "gl-clienttype": GL_CLIENTTYPE,
            "gl-deviceid": device_id,
            "gl-version": self.gl_version,
            "gl-nonce": nonce,
            "gl-curtime": str(int(time.time())),
        }

        try:
            resp = self.session.post(signed_url, json=payload, headers=headers, timeout=15)
            data = resp.json()

            if data.get('code') == 200:
                result = data.get('result', {})
                token = result.get('token', '')
                uid = result.get('userInfo', {}).get('user', {}).get('uid', '')
                source = result.get('source', 'URS')
                if uid and token:
                    logger.info(f'登录成功! Token: {token[:16]}...')
                    return {
                        'GL_UID': uid,
                        'GL_TOKEN': token,
                        'GL_SOURCE': source,
                        'GL_DEVICEID': device_id,
                    }
                logger.warning('登录API返回200但缺少uid或token')
                return None
            else:
                logger.warning(f'登录失败: code={data.get("code")}, msg={data.get("errmsg")}')
                return None
        except Exception as e:
            logger.warning(f'登录请求异常: {e}')
            return None

    # ======================== HTTP API ========================

    def _get_role_info(self):
        """通过大神API获取绑定的阴阳师角色信息"""
        url = f"{LOGIN_BASE}/v1/app/gameRole/getBindList"
        payload = {"uid": self.gl_uid}

        try:
            resp = self.session.post(url, json=payload, headers=self._build_headers(), timeout=15)
            data = resp.json()
            if data.get('code') != 200:
                logger.warning(f'获取角色信息失败: {data.get("errmsg")}')
                return None

            roles = data.get('result', [])
            for role in roles:
                if role.get('appKey') == self.app_key:
                    role_id = role.get('roleId', '')
                    server = role.get('server', '')
                    if role_id:
                        logger.info(f'API获取角色成功: {role_id} @ {server}')
                        return {'roleId': role_id, 'server': server}

            if roles:
                logger.warning(f'找到 {len(roles)} 个绑定角色，但无 appKey={self.app_key} 的角色')
            else:
                logger.warning('未找到任何绑定角色')
            return None
        except Exception as e:
            logger.warning(f'获取角色信息异常: {e}')
            return None

    def _is_token_expired(self, code, msg):
        """判断API返回是否表示Token已过期"""
        if code in [802, 805]:
            return True
        if msg and ('其他设备' in msg or '登录' in msg or '过期' in msg or '失效' in msg):
            return True
        return False

    def _relogin(self):
        """Token过期时重新登录，更新 self 上的凭据。返回是否成功。"""
        logger.warning('Token已失效，尝试重新登录...')
        pid = self.frida_pid or self._get_app_pid()
        if not pid:
            logger.error('重新登录失败：APP未运行')
            return False
        _, token_data = self._auto_login(pid)
        if not token_data:
            logger.error('重新登录失败')
            return False
        self.gl_uid = token_data.get('GL_UID', '')
        self.gl_token = token_data.get('GL_TOKEN', '')
        self.gl_deviceid = token_data.get('GL_DEVICEID', self.gl_deviceid)
        self.gl_source = token_data.get('GL_SOURCE', 'URS')
        logger.info(f'重新登录成功! 新Token: {self.gl_token[:16]}...')
        return True

    def _generate_nonce(self):
        return str(random.randint(-9000000000000000000, 9000000000000000000))

    def _build_headers(self, nonce=None):
        if not nonce:
            nonce = self._generate_nonce()
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"Mozilla/5.0 (Linux; Android 12) Godlike/{self.gl_version}",
            "gl-version": self.gl_version,
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

            code = data.get('code')
            msg = data.get('errmsg', '')

            # Token过期，重新登录后重试
            if code != 200 and self._is_token_expired(code, msg):
                if self._relogin():
                    resp = self.session.post(url, json=payload, headers=self._build_headers(), timeout=15)
                    data = resp.json()
                    code = data.get('code')
                    msg = data.get('errmsg', '')

            if code != 200:
                logger.warning(f'获取礼包失败: {msg}')
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
            elif self._is_token_expired(code, msg):
                # Token过期，重新登录后重试
                if self._relogin():
                    logger.info(f'  重试领取: {title}...')
                    nonce = self._generate_nonce()
                    sign_headers["GL-Token"] = self.gl_token
                    sign_headers["GL-Nonce"] = nonce
                    signed_url = self._frida_sign(base_url, json.dumps(payload), sign_headers)
                    if signed_url:
                        resp2 = self.session.post(signed_url, json=payload,
                                                  headers=self._build_headers(nonce), timeout=15)
                        data2 = resp2.json()
                        if data2.get('code') == 200:
                            logger.info(f'  领取成功: {title}')
                            return True
                        logger.warning(f'  重试失败: {title} - {data2.get("errmsg")}')
            else:
                logger.warning(f'  领取失败: {title} - {msg}')

        except Exception as e:
            logger.error(f'  领取异常: {title} - {e}')

        return False
