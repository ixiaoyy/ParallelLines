"""不依赖部署中的进程；仅根据本任务事务恢复自有容器与唯一主站配置段。"""

import json
import sys

from deploy import DeployError, rollback_application
from managed_config import ManagedConfigError
from release_contract import ContractError
from tls import OperationError


def main(arguments):
    """rollback 必须指明当前/未完成应用版本，不接受目录、URL、shell 或整个工作树目标。"""
    if len(arguments) != 2 or arguments[0] != "rollback":
        print(json.dumps({"operation": "rejected", "complete": False, "errors": ["invalid_rollback_arguments"]}))
        return 2
    report = {"operation": "rollback", "complete": False, "errors": []}
    try:
        rollback_application(arguments[1], report)
    except (DeployError, ContractError, ManagedConfigError, OperationError) as error:
        report["errors"].append(str(error))
    except (OSError, ValueError, KeyError, TypeError) as error:
        report["errors"].append("tools_rollback:" + type(error).__name__)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["complete"] and not report["errors"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
