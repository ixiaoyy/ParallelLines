import { useState } from "react";
import {
  ApiOutlined,
  CheckCircleFilled,
  ClockCircleOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  ExclamationCircleFilled,
  FieldTimeOutlined,
  MailOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SendOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import "./AdminPages.css";

const serviceItems = [
  { name: "API 服务", detail: "FastAPI · 2 个实例", latency: "42 ms", state: "运行正常", icon: ApiOutlined, tone: "success" },
  { name: "主数据库", detail: "MySQL · 连接池 18 / 50", latency: "16 ms", state: "运行正常", icon: DatabaseOutlined, tone: "success" },
  { name: "缓存服务", detail: "Redis · 内存 38%", latency: "3 ms", state: "运行正常", icon: CloudServerOutlined, tone: "success" },
  { name: "邮件服务", detail: "SMTP · 最近 5 分钟", latency: "1 次失败", state: "需要留意", icon: MailOutlined, tone: "warning" },
];

const mailLogs = [
  { id: "mail-10042", subject: "每周社区摘要", recipient: "186 位订阅用户", time: "10:31:42", duration: "18.4 秒", status: "部分失败" },
  { id: "mail-10041", subject: "登录验证码", recipient: "linyu@example.com", time: "10:16:08", duration: "0.8 秒", status: "已发送" },
  { id: "mail-10040", subject: "新回复提醒", recipient: "xia@example.com", time: "09:58:31", duration: "1.1 秒", status: "已发送" },
  { id: "mail-10039", subject: "账号验证", recipient: "frontier-bot-0623153909@example.com", time: "09:42:10", duration: "0.9 秒", status: "已发送" },
];

/**
 * 展示服务健康度、异步任务队列与邮件日志，并提供原型级刷新和失败任务重试。
 * 重试与刷新仅改变本地视觉状态，不会连接生产服务。
 */
export function SystemPage() {
  const [refreshed, setRefreshed] = useState(false);
  const [logFilter, setLogFilter] = useState("all");
  const [jobs, setJobs] = useState([
    { id: "job-7841", name: "生成每日社区摘要", queue: "content", created: "10:44", status: "执行中", progress: "68%" },
    { id: "job-7840", name: "发送每周社区摘要", queue: "mail", created: "10:31", status: "失败", progress: "186 / 192" },
    { id: "job-7839", name: "同步访问统计汇总", queue: "analytics", created: "10:15", status: "已完成", progress: "100%" },
    { id: "job-7838", name: "清理过期登录会话", queue: "maintenance", created: "10:00", status: "已完成", progress: "100%" },
  ]);
  const visibleLogs = mailLogs.filter((log) => logFilter === "all" || (logFilter === "success" ? log.status === "已发送" : log.status !== "已发送"));

  return (
    <div className="admin-page system-page">
      <header className="admin-page__header">
        <div>
          <p className="admin-page__eyebrow">基础设施</p>
          <h1>系统运行</h1>
          <p>查看核心服务、后台任务和邮件发送状态。</p>
        </div>
        <button type="button" className="admin-refresh-button" onClick={() => setRefreshed(true)}>
          <ReloadOutlined aria-hidden="true" className={refreshed ? "is-spinning-once" : ""} />
          刷新状态
        </button>
      </header>

      <div className="system-overall-status" role="status">
        <span className="system-overall-status__signal"><CheckCircleFilled aria-hidden="true" /></span>
        <div><strong>核心服务运行正常</strong><p>邮件队列有 1 个任务需要人工确认，其余指标均在正常范围内。</p></div>
        <time><ClockCircleOutlined aria-hidden="true" /> {refreshed ? "刚刚更新" : "30 秒前更新"}</time>
      </div>

      <section className="admin-flat-section system-services">
        <div className="admin-section-heading">
          <div><p className="admin-section-heading__kicker">实时检测</p><h2>服务状态</h2></div>
          <span className="admin-section-heading__count">3 正常 · 1 提醒</span>
        </div>
        <div className="system-service-list">
          {serviceItems.map((service) => {
            const Icon = service.icon;
            return (
              <div className="system-service-row" key={service.name}>
                <span className={`system-service-row__icon is-${service.tone}`}><Icon aria-hidden="true" /></span>
                <div><strong>{service.name}</strong><small>{service.detail}</small></div>
                <span className="system-service-row__latency">{service.latency}</span>
                <span className={`admin-status-pill is-${service.tone}`}>
                  {service.tone === "success" ? <CheckCircleFilled aria-hidden="true" /> : <ExclamationCircleFilled aria-hidden="true" />}
                  {service.state}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      <section className="admin-flat-section system-queue">
        <div className="admin-section-heading">
          <div><p className="admin-section-heading__kicker">异步任务</p><h2>任务队列</h2></div>
          <div className="system-queue-summary"><span>等待 <strong>2</strong></span><span>执行中 <strong>1</strong></span><span>失败 <strong>1</strong></span></div>
        </div>
        <div className="admin-data-table system-queue-table">
          <div className="admin-data-table__head"><span>任务</span><span>队列</span><span>创建时间</span><span>进度</span><span>状态</span><span>操作</span></div>
          {jobs.map((job) => (
            <div className="admin-data-table__row" key={job.id}>
              <span className="system-job-name"><FieldTimeOutlined aria-hidden="true" /><span><strong>{job.name}</strong><small>{job.id}</small></span></span>
              <code>{job.queue}</code>
              <time>{job.created}</time>
              <span>{job.progress}</span>
              <span className={`admin-status-pill${job.status === "已完成" ? " is-success" : job.status === "失败" ? " is-danger" : " is-info"}`}>
                {job.status === "执行中" || job.status === "重试中" ? <SyncOutlined spin aria-hidden="true" /> : job.status === "失败" ? <ExclamationCircleFilled aria-hidden="true" /> : <CheckCircleFilled aria-hidden="true" />}
                {job.status}
              </span>
              <span>
                {job.status === "失败" ? (
                  <button
                    type="button"
                    className="admin-table-action"
                    onClick={() => setJobs((items) => items.map((item) => item.id === job.id ? { ...item, status: "重试中", progress: "准备中" } : item))}
                  >
                    <PlayCircleOutlined aria-hidden="true" /> 重试
                  </button>
                ) : <span className="admin-table-action-placeholder">—</span>}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="admin-flat-section system-logs">
        <div className="admin-section-heading">
          <div><p className="admin-section-heading__kicker">最近 24 小时</p><h2>邮件日志</h2></div>
          <div className="admin-segmented-control" aria-label="邮件日志筛选">
            <button type="button" className={logFilter === "all" ? "is-active" : ""} onClick={() => setLogFilter("all")}>全部</button>
            <button type="button" className={logFilter === "success" ? "is-active" : ""} onClick={() => setLogFilter("success")}>已发送</button>
            <button type="button" className={logFilter === "failed" ? "is-active" : ""} onClick={() => setLogFilter("failed")}>异常</button>
          </div>
        </div>
        <div className="admin-data-table system-log-table">
          <div className="admin-data-table__head"><span>邮件</span><span>收件人</span><span>时间</span><span>耗时</span><span>结果</span></div>
          {visibleLogs.map((log) => (
            <div className="admin-data-table__row" key={log.id}>
              <span className="system-mail-subject"><SendOutlined aria-hidden="true" /><span><strong>{log.subject}</strong><small>{log.id}</small></span></span>
              <span className="system-log-recipient">{log.recipient}</span>
              <time>{log.time}</time>
              <span>{log.duration}</span>
              <span className={`admin-status-pill${log.status === "已发送" ? " is-success" : " is-warning"}`}>{log.status}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export default SystemPage;
