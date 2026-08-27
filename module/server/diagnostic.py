# This Python file uses the following encoding: utf-8
# @author runhey
"""导出脱敏后的配置摘要与最近日志为 zip，用于风控对照分析。不导出账号/token/密码。"""
import json
import platform
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from module.config.utils import read_file, deep_get
from module.server.config_manager import ConfigManager
from module.logger import logger

PROJECT_ROOT = Path.cwd().resolve()
LOG_DIR = PROJECT_ROOT / 'log'
OUT_DIR = LOG_DIR / 'diagnostic'

_RECENT_INSTANCE_LOGS = 4
_RECENT_SHARED_LOGS = 3
_RECENT_ERROR_LOGS = 10

# 白名单：只导出这些字段，不带出 URS 凭据
_DEVICE_FIELDS = [
    'control_method', 'screenshot_method', 'serial', 'package_name',
    'emulatorinfo_type', 'emulatorinfo_name',
]

# 值匹配到分隔符为止(涵盖 base64 的 +/= 等), 避免只按 \w 截断导致凭据残留
_V = r'[^\s"\',:;&?{}\[\]]'
_SCRUB_PATTERNS = [
    (re.compile(r'(账号[:：]\s*)(' + _V + r'{3,})'), r'\1***'),
    (re.compile(r'(account["\'\s:：=]+)(' + _V + r'{3,})', re.I), r'\1***'),
    (re.compile(r'(token["\'\s:：=]+)(' + _V + r'{6,})', re.I), r'\1***'),
    (re.compile(r'(urs[\w]*["\'\s:：=]+)(' + _V + r'{6,})', re.I), r'\1***'),
    (re.compile(r'(password["\'\s:：=]+)(' + _V + r'+)', re.I), r'\1***'),
    (re.compile(r'\b(1[3-9]\d)\d{4}(\d{4})\b'), r'\1****\2'),
]


def _scrub(text: str) -> str:
    for pat, repl in _SCRUB_PATTERNS:
        text = pat.sub(repl, text)
    return text


def _config_summary(name: str) -> dict:
    data = read_file(str(PROJECT_ROOT / 'config' / f'{name}.json'))
    if not isinstance(data, dict):
        return {'instance': name, 'error': 'config unreadable'}
    device = {k: deep_get(data, f'script.device.{k}') for k in _DEVICE_FIELDS}
    optimization = data.get('script', {}).get('optimization', {})
    anti_ban = data.get('script', {}).get('anti_ban', {})
    enabled = []
    for task, cfg in data.items():
        if isinstance(cfg, dict) and deep_get(cfg, 'scheduler.enable') is True:
            enabled.append(task)
    return {
        'instance': name,
        'device': device,
        'optimization': optimization,
        'anti_ban': anti_ban,
        'enabled_tasks': sorted(enabled),
    }


def _recent_files(pattern: str, limit: int) -> list:
    try:
        candidates = [p for p in LOG_DIR.glob(pattern) if p.is_file()]
    except OSError:
        return []
    recent = []
    for p in candidates:
        try:
            recent.append((p.stat().st_mtime, p))
        except OSError:
            continue
    recent.sort(key=lambda item: item[0], reverse=True)
    return [p for _, p in recent[:limit]]


def build_diagnostic_zip(config_name: str = '') -> Path:
    """config_name 为空或 'Home' 时导出全部实例。"""
    # 只接受已存在的实例名, 防止 config_name 带 ../ 造成路径穿越
    valid = ConfigManager.all_script_files()
    if config_name and config_name in valid:
        instances = [config_name]
        tag = config_name
    else:
        instances = valid
        tag = 'all'

    summary = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'platform': platform.platform(),
        'python': sys.version.split()[0],
        'instances': [_config_summary(n) for n in instances],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    zip_path = OUT_DIR / f'oas_diag_{tag}_{stamp}.zip'

    log_files = []
    for name in instances:
        log_files += _recent_files(f'*_{name}.txt', _RECENT_INSTANCE_LOGS)
    log_files += _recent_files('*_api.txt', _RECENT_SHARED_LOGS)
    log_files += _recent_files('*_server.txt', _RECENT_SHARED_LOGS)

    error_logs = []
    error_root = LOG_DIR / 'error'
    if error_root.exists():
        try:
            err = [p for p in error_root.glob('*/log.txt') if p.is_file()]
            err.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            error_logs = err[:_RECENT_ERROR_LOGS]
        except OSError:
            error_logs = []

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('summary.json', json.dumps(summary, ensure_ascii=False, indent=2))
        for f in dict.fromkeys(log_files):
            try:
                zf.writestr(f'log/{f.name}', _scrub(f.read_text(encoding='utf-8', errors='replace')))
            except OSError as e:
                logger.warning(f'diagnostic: skip {f}: {e}')
        for f in error_logs:
            try:
                zf.writestr(f'error/{f.parent.name}/log.txt',
                            _scrub(f.read_text(encoding='utf-8', errors='replace')))
            except OSError as e:
                logger.warning(f'diagnostic: skip {f}: {e}')

    logger.info(f'诊断日志已导出: {zip_path}')
    return zip_path
