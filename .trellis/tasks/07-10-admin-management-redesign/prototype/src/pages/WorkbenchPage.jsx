import { useState } from "react";
import {
  AlertOutlined,
  ArrowRightOutlined,
  AuditOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  FlagOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  TeamOutlined,
  UserAddOutlined,
} from "@ant-design/icons";
import "./AdminPages.css";

const summaryItems = [
  { label: "待审核内容", value: "12", note: "较昨日 +4", icon: AuditOutlined, target: "moderation" },
  { label: "今日新增用户", value: "2", note: "不含马甲账号", icon: UserAddOutlined, target: "analytics" },
  { label: "未处理举报", value: "3", note: "1 项已等待 2 小时", icon: FlagOutlined, target: "moderation" },
  { label: "队列健康度", value: "98.7%", note: "1 个任务待重试", icon: SafetyCertificateOutlined, target: "system" },
];

const quickLinks = [
  { label: "查看增长数据", description: "访问、访客与真实用户增长", icon: BarChartOutlined, target: "analytics" },
  { label: "管理用户", description: "账号状态、角色与成长信息", icon: TeamOutlined, target: "users" },
  { label: "处理审核", description: "主题、回复与举报队列", icon: AuditOutlined, target: "moderation" },
  { label: "检查系统", description: "服务、任务队列与邮件日志", icon: SettingOutlined, target: "system" },
];

const activityItems = [
  { person: "administrator", action: "通过主题", subject: "每日金句｜第023天：你的善良，必须带点锋芒", time: "10:42" },
  { person: "administrator", action: "调整用户状态", subject: "frontier_bot_0623153909 · 等待验证", time: "09:18" },
  { person: "系统", action: "完成邮件任务", subject: "每周社区摘要 · 186 封", time: "08:30" },
];

/**
 * 展示后台工作台，并通过 onNavigate(pageKey) 将快捷入口交给外层壳层切换页面。
 * 页面内的异常提醒可被标记处理，状态仅保存在当前原型会话中。
 */
export function WorkbenchPage({ onNavigate }) {
  const [alerts, setAlerts] = useState([
    {
      id: "queue",
      tone: "warning",
      title: "邮件发送队列出现 1 个失败任务",
      detail: "社区周报 · 已自动重试 2 次 · 10:31",
      action: "查看任务",
      target: "system",
    },
    {
      id: "report",
      tone: "danger",
      title: "1 条举报即将超过处理时限",
      detail: "举报 #RP-0710-018 · 已等待 1 小时 48 分",
      action: "立即处理",
      target: "moderation",
    },
    {
      id: "growth",
      tone: "info",
      title: "昨日真实用户增长低于近 7 日均值",
      detail: "昨日新增 1 人 · 近 7 日均值 1.7 人",
      action: "查看增长",
      target: "analytics",
    },
  ]);

  return (
    <div className="admin-page workbench-page">
      <header className="admin-page__header">
        <div>
          <p className="admin-page__eyebrow">运营总览</p>
          <h1>工作台</h1>
          <p>集中处理今天最重要的社区运营事项。</p>
        </div>
        <div className="admin-page__date">
          <ClockCircleOutlined aria-hidden="true" />
          <span>2026 年 7 月 10 日</span>
          <strong>星期五</strong>
        </div>
      </header>

      <section className="admin-summary-strip" aria-label="今日运营摘要">
        {summaryItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              className="admin-summary-item"
              type="button"
              key={item.label}
              onClick={() => onNavigate?.(item.target)}
            >
              <span className="admin-summary-item__label">{item.label}</span>
              <span className="admin-summary-item__value-row">
                <strong>{item.value}</strong>
                <Icon aria-hidden="true" />
              </span>
              <span className="admin-summary-item__note">{item.note}</span>
            </button>
          );
        })}
      </section>

      <div className="workbench-grid">
        <section className="admin-flat-section">
          <div className="admin-section-heading">
            <div>
              <p className="admin-section-heading__kicker">待办事项</p>
              <h2>今天需要处理</h2>
            </div>
            <span className="admin-section-heading__count">共 18 项</span>
          </div>

          <div className="workbench-tasks">
            <button className="workbench-task" type="button" onClick={() => onNavigate?.("moderation")}>
              <span className="workbench-task__icon is-blue"><AuditOutlined aria-hidden="true" /></span>
              <span className="workbench-task__body">
                <strong>审核新提交内容</strong>
                <small>8 个主题 · 4 条回复</small>
              </span>
              <span className="workbench-task__meta">12 项</span>
              <ArrowRightOutlined aria-hidden="true" />
            </button>
            <button className="workbench-task" type="button" onClick={() => onNavigate?.("moderation")}>
              <span className="workbench-task__icon is-orange"><FlagOutlined aria-hidden="true" /></span>
              <span className="workbench-task__body">
                <strong>处理用户举报</strong>
                <small>最早一条于 08:54 提交</small>
              </span>
              <span className="workbench-task__meta is-urgent">3 项</span>
              <ArrowRightOutlined aria-hidden="true" />
            </button>
            <button className="workbench-task" type="button" onClick={() => onNavigate?.("users")}>
              <span className="workbench-task__icon is-green"><UserAddOutlined aria-hidden="true" /></span>
              <span className="workbench-task__body">
                <strong>确认待验证账号</strong>
                <small>注册超过 24 小时仍未验证</small>
              </span>
              <span className="workbench-task__meta">2 人</span>
              <ArrowRightOutlined aria-hidden="true" />
            </button>
          </div>
        </section>

        <section className="admin-flat-section workbench-alerts" aria-live="polite">
          <div className="admin-section-heading">
            <div>
              <p className="admin-section-heading__kicker">需要留意</p>
              <h2>异常提醒</h2>
            </div>
            <span className="admin-section-heading__count">{alerts.length} 条</span>
          </div>

          {alerts.length > 0 ? (
            <div className="workbench-alert-list">
              {alerts.map((alert) => (
                <article className={`workbench-alert is-${alert.tone}`} key={alert.id}>
                  <span className="workbench-alert__icon">
                    {alert.tone === "danger" ? <ExclamationCircleOutlined aria-hidden="true" /> : <AlertOutlined aria-hidden="true" />}
                  </span>
                  <div>
                    <strong>{alert.title}</strong>
                    <p>{alert.detail}</p>
                    <div className="workbench-alert__actions">
                      <button type="button" onClick={() => onNavigate?.(alert.target)}>{alert.action}</button>
                      <button type="button" onClick={() => setAlerts((items) => items.filter((item) => item.id !== alert.id))}>标记已知</button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="admin-empty-state is-compact">
              <CheckCircleOutlined aria-hidden="true" />
              <strong>提醒已全部处理</strong>
              <span>当前没有需要留意的异常。</span>
            </div>
          )}
        </section>
      </div>

      <section className="admin-flat-section admin-quick-section">
        <div className="admin-section-heading">
          <div>
            <p className="admin-section-heading__kicker">常用功能</p>
            <h2>快捷入口</h2>
          </div>
        </div>
        <div className="admin-quick-grid">
          {quickLinks.map((item) => {
            const Icon = item.icon;
            return (
              <button type="button" className="admin-quick-link" key={item.label} onClick={() => onNavigate?.(item.target)}>
                <Icon aria-hidden="true" />
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </span>
                <ArrowRightOutlined aria-hidden="true" />
              </button>
            );
          })}
        </div>
      </section>

      <section className="admin-flat-section workbench-activity">
        <div className="admin-section-heading">
          <div>
            <p className="admin-section-heading__kicker">最近 24 小时</p>
            <h2>管理动态</h2>
          </div>
          <button type="button" className="admin-text-button">查看审计日志 <ArrowRightOutlined aria-hidden="true" /></button>
        </div>
        <div className="workbench-activity-list">
          {activityItems.map((item) => (
            <div className="workbench-activity-row" key={`${item.time}-${item.subject}`}>
              <span className="workbench-activity-row__status"><CheckCircleOutlined aria-hidden="true" /></span>
              <strong>{item.person}</strong>
              <span>{item.action}</span>
              <span className="workbench-activity-row__subject">{item.subject}</span>
              <time>{item.time}</time>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export default WorkbenchPage;
