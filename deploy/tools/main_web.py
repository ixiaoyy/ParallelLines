"""主站 Web 窄发布：独立只读规格盘点，以及显式授权的单服务/两处入口事务。"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


WEB = "parallellines-web-1"
GATEWAY = "parallellines-nginx-1"
PROJECT = "parallellines"
NETWORK = "parallellines_default"
MAIN_CONFIG = Path("/opt/parallellines/deploy/nginx/default.conf")
MAX_OUTPUT = 1024 * 1024


class MainWebError(Exception):
    """稳定错误码，不回显环境、配置正文或命令的原始错误输出。"""


def command(label, arguments, timeout=12, accepted=(0,)):
    """执行固定 argv 并限定时间/结果；不使用 shell，不读取 .env。"""
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise MainWebError(label + ":timeout") from None
    except OSError as error:
        raise MainWebError(label + ":" + type(error).__name__) from None
    if result.returncode not in accepted:
        raise MainWebError(label + ":exit_" + str(result.returncode))
    if len(result.stdout) + len(result.stderr) > MAX_OUTPUT:
        raise MainWebError(label + ":output_limit")
    return result


def web_metadata():
    """读取 Web 公共规格白名单，不请求 Config.Env、完整 labels 或完整 inspect。"""
    fields = {
        "id": ".Id", "image_id": ".Image", "image": ".Config.Image", "running": ".State.Running",
        "project": '(index .Config.Labels "com.docker.compose.project")',
        "service": '(index .Config.Labels "com.docker.compose.service")',
        "working_directory": '(index .Config.Labels "com.docker.compose.project.working_dir")',
        "compose_files": '(index .Config.Labels "com.docker.compose.project.config_files")',
        "container_number": '(index .Config.Labels "com.docker.compose.container-number")',
        "entrypoint": ".Config.Entrypoint", "command": ".Config.Cmd", "user": ".Config.User",
        "workdir": ".Config.WorkingDir", "exposed_ports": ".Config.ExposedPorts", "healthcheck": ".Config.Healthcheck",
        "mounts": ".Mounts", "restart": ".HostConfig.RestartPolicy", "port_bindings": ".HostConfig.PortBindings",
        "read_only": ".HostConfig.ReadonlyRootfs", "privileged": ".HostConfig.Privileged",
        "network_mode": ".HostConfig.NetworkMode", "memory": ".HostConfig.Memory", "nano_cpus": ".HostConfig.NanoCpus",
        "cpu_shares": ".HostConfig.CpuShares", "pids_limit": ".HostConfig.PidsLimit", "init": ".HostConfig.Init",
        "cap_add": ".HostConfig.CapAdd", "cap_drop": ".HostConfig.CapDrop", "security_opt": ".HostConfig.SecurityOpt",
    }
    template = "{" + ",".join(json.dumps(key) + ":{{json " + value + "}}" for key, value in fields.items()) + ","
    template += '"networks":"{{range $name, $network := .NetworkSettings.Networks}}{{$name}} {{end}}"}'
    value = json.loads(command("main_web_metadata", ["docker", "inspect", "--format", template, WEB]).stdout)
    value["networks"] = sorted(value["networks"].split())
    if value.get("project") != PROJECT or value.get("service") != "web" or value.get("running") is not True:
        raise MainWebError("main_web_not_running_in_expected_project")
    if not re.fullmatch(r"[0-9a-f]{64}", value.get("id", "")):
        raise MainWebError("main_web_identifier_invalid")
    # 只输出已知静态 Nginx 命令；若被他人改为未知命令，不回显可能夹带的参数。
    if value.get("entrypoint") != ["/docker-entrypoint.sh"] or value.get("command") != ["nginx", "-g", "daemon off;"]:
        raise MainWebError("main_web_command_not_approved")
    check = value.get("healthcheck") or {}
    if check.get("Test") != ["CMD-SHELL", "wget -qO- http://127.0.0.1/ >/dev/null || exit 1"]:
        raise MainWebError("main_web_healthcheck_not_approved")
    return value


def gateway_metadata():
    """核固定 gateway 的公开身份、只读配置 bind 和宿主/容器的同一 inode。"""
    template = ('{"id":{{json .Id}},"running":{{json .State.Running}},"mounts":{{json .Mounts}},'
                '"networks":"{{range $name, $network := .NetworkSettings.Networks}}{{$name}} {{end}}"}')
    item = json.loads(command("main_gateway_metadata", ["docker", "inspect", "--format", template, GATEWAY]).stdout)
    if item.get("running") is not True or NETWORK not in item.get("networks", "").split():
        raise MainWebError("main_gateway_not_in_approved_context")
    mount = [value for value in item["mounts"] if value.get("Type") == "bind" and value.get("Source") == str(MAIN_CONFIG)
             and value.get("Destination") == "/etc/nginx/conf.d/default.conf" and value.get("RW") is False]
    if len(mount) != 1 or MAIN_CONFIG.is_symlink() or not MAIN_CONFIG.is_file():
        raise MainWebError("main_gateway_configuration_bind_changed")
    identity = MAIN_CONFIG.stat()
    inode = command("main_gateway_inode", ["docker", "exec", GATEWAY, "stat", "-c", "%d:%i", "/etc/nginx/conf.d/default.conf"]).stdout.strip()
    if inode != str(identity.st_dev) + ":" + str(identity.st_ino):
        raise MainWebError("main_gateway_inode_does_not_match_host")
    return {"id": item["id"], "config_identity": {"device": identity.st_dev, "inode": identity.st_ino},
            "configuration_bind_read_only": True, "network": NETWORK}


def inventory():
    """只读现场规格，用于确定下一次显式 Web 发布的固定配置；不创建状态/目录。"""
    started = time.monotonic()
    web, gateway = web_metadata(), gateway_metadata()
    return {"operation": "main-web-inventory", "read_only": True, "complete": True,
            "web": web, "gateway": gateway, "elapsed_seconds": round(time.monotonic() - started, 3)}


def main(arguments):
    """当前只开放已完成的只读盘点，写入口完成实际规格核对后才加入。"""
    report = {"operation": arguments[0] if arguments else "rejected", "complete": False, "errors": []}
    try:
        if arguments != ["main-web-inventory"]:
            raise MainWebError("unsupported_main_web_operation")
        report = inventory()
    except MainWebError as error:
        report["errors"].append(str(error))
    except (OSError, ValueError, KeyError, TypeError) as error:
        report["errors"].append("main_web:" + type(error).__name__)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
