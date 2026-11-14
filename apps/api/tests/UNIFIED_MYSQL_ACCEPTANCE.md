# 统一登录 MySQL 并发验收

本文件只说明 `test_unified_auth_mysql.py` 的增量验收，不替代 `docs/UNIFIED_LOGIN.md` 的跨站发布合同。

## 隔离边界

- 从当前 Git index 导出 API 候选，不在混入另一轮 Space 的工作区启动应用或打包。
- 使用已授权的独占 `mysql:8.4` 临时容器；端口只绑定 `127.0.0.1:13316`，独立 Docker volume，不挂生产目录。
- 数据库名必须为 `pl_unified_acceptance_` 加 12 位十六进制后缀，且初始为空。
- 使用仅为本次容器生成的临时凭据，通过环境传递，不写入仓库、命令回执或发布包。
- 夹具只建立既有 `users`、`user_sessions`、`user_security_tokens` 三表；2 个用户和 5 个会话均为合成数据。
  用例结束仅清理自身创建的三表，容器/volume 由该临时环境所有者清理。
- `UNIFIED_MYSQL_TEST_URL` 缺失时跳过；设置后不满足安全边界就失败，不能回落到应用 `DATABASE_URL`。

## 从 index 运行

使用新建且为空的候选目录；不要复制整个当前工作区，也不要用 `git stash` 或覆盖 Space 变更。
以下导出只读取 index，测试文件另按显式清单加入；依赖继续使用原仓库已安装的 API 虚拟环境。

```powershell
# 在 ParallelLines 仓库根目录执行，$candidate 必须是本次新建的专用临时目录。
# 用 Python 的 subprocess 传递 NUL 分隔文件名，避免 PowerShell 改写路径或字节。
$env:UNIFIED_INDEX_CANDIDATE = $candidate
@'
import os, subprocess
from pathlib import Path
target = Path(os.environ['UNIFIED_INDEX_CANDIDATE']).resolve()
if target.exists():
    raise SystemExit('候选目录已存在，拒绝覆盖')
target.mkdir(parents=True)
files = subprocess.check_output(['git', 'ls-files', '-z', '--', 'apps/api'])
subprocess.run(['git', 'checkout-index', '-z', '--stdin', '--prefix='+target.as_posix()+'/'],
               input=files, check=True)
source = Path('apps/api/tests/test_unified_auth_mysql.py')
(target/source).write_bytes(source.read_bytes())
assert not (target/'apps/api/app/models/space.py').exists()
assert 'from .space import' not in (target/'apps/api/app/models/__init__.py').read_text()
assert 'app.models.space' not in (target/'apps/api/app/models/__init__.py').read_text()
'@ | .\apps\api\.venv\Scripts\python.exe -

# URL 仅指向本次隔离容器；不打印其内容。同名标记是临时表 DDL 的明确选择。
$env:UNIFIED_MYSQL_TEST_URL = $localTestUrl
$env:UNIFIED_MYSQL_ALLOW_DDL = $temporaryDatabaseName
Push-Location "$candidate/apps/api"
try {
  & $originalApiPython -m pytest -q tests/test_unified_auth_mysql.py
} finally {
  Pop-Location
  Remove-Item Env:UNIFIED_MYSQL_TEST_URL,Env:UNIFIED_MYSQL_ALLOW_DDL,Env:UNIFIED_INDEX_CANDIDATE
}
```

根级前端/API 完整发布产物同样应从 index 独立导出后构建；如需回归未暂存测试，只复制明确的本次测试清单。
不能把测试通过后的混合工作区直接当发布源。

## 决定性检查

| 路径 | 实际并发与断言 |
| --- | --- |
| 浏览器指针换号 | A→B 持有真实行锁；另一连接携带旧代际 A 请求新 sid30，确认数据库 `LOCK WAIT`；放锁后必须撤掉真正前一 sid20，其他设备 sid11/21 不受影响 |
| RR 快照后的身份撤销 | 初次 bearer 一致性读取后，由另一连接撤销新 sid 或停用新用户；最终锁定读取必须拒绝，旧浏览器 sid10 与 Cookie 不变 |
| 授权码双兑换 | 第一连接持有授权码行锁，第二连接实际 `LOCK WAIT`；第一连接提交后第二连接拒绝重放，只成功一次 |
| 旧退出票与换号交错 | 旧票据请求排在换号指针锁后；放锁后只处理旧 sid，不向新身份响应 `Set-Cookie` 删除，新 Cookie 可继续读取 B |

引擎明确使用 MySQL `REPEATABLE READ`；连接、响应、锁等待观察和协程等待均有上限。
锁等待观察需要专属临时库账号可读 `information_schema.innodb_trx`，不应为此给生产应用账号增加权限。
`TRX_STATE`、线程映射和 `PROCESS` 要求见 [MySQL 8.4 INNODB_TRX](https://dev.mysql.com/doc/refman/8.4/en/information-schema-innodb-trx-table.html)；
RR 一致性快照与锁定读取的差异见 [MySQL 8.4 一致性读取](https://dev.mysql.com/doc/refman/8.4/en/innodb-consistent-read.html)。
MySQL 通过只证明上述 ORM/事务路径，不代表真实浏览器 Cookie、OIDC、模型计费、Nginx 或生产上线已经验收。

## Nginx 验收

三份实际配置为 `deploy/nginx/default.conf`、`deploy/nginx/forum.conf`、`apps/web/nginx.conf`；不存在 `apps/web/nginx.forum.conf`。
需要对 index 候选安装进临时 Nginx 容器后的完整有效配置执行 `nginx -t`，并在代理端实际检查私密页面头和恢复入口 404。
TLS 只使用临时 CA/测试证书，固定主域/forum/chat/api 别名；不要复制生产私钥，也不要把主机名改成 localhost 来放宽合同。
静态正则/块配对结果不能代替该检查。
