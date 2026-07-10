import { useState } from "react";
import {
  BellOutlined,
  CloseOutlined,
  DashboardOutlined,
  DownOutlined,
  ExportOutlined,
  LineChartOutlined,
  MenuOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  UserOutlined,
} from "@ant-design/icons";
import "./AdminShell.css";

const ADMIN_SECTIONS = [
  {
    id: "dashboard",
    label: "工作台",
    mobileLabel: "工作台",
    icon: <DashboardOutlined />,
  },
  {
    id: "analytics",
    label: "访问与增长",
    mobileLabel: "增长",
    icon: <LineChartOutlined />,
  },
  {
    id: "users",
    label: "用户管理",
    mobileLabel: "用户",
    icon: <UserOutlined />,
  },
  {
    id: "moderation",
    label: "内容审核",
    mobileLabel: "审核",
    icon: <SafetyCertificateOutlined />,
  },
  {
    id: "system",
    label: "系统运行",
    mobileLabel: "系统",
    icon: <SettingOutlined />,
  },
];

/**
 * 为后台各业务页提供统一导航、顶栏和移动端抽屉。
 * @param {object} props 组件属性。
 * @param {string} props.activeSection 当前激活的导航项 ID。
 * @param {(sectionId: string) => void} props.onNavigate 导航切换回调。
 * @param {React.ReactNode} props.children 当前业务页面内容。
 * @param {() => void} [props.onReturnToSite] 返回主站回调。
 * @param {string} [props.adminName] 当前管理员名称。
 * @param {string} [props.adminRole] 当前管理员角色。
 * @param {number} [props.notificationCount] 未读通知数。
 * @returns {React.ReactElement} 后台共享壳层。
 */
export function AdminShell({
  activeSection,
  onNavigate,
  children,
  onReturnToSite,
  adminName = "administrator",
  adminRole = "超级管理员",
  notificationCount = 3,
}) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const activeItem =
    ADMIN_SECTIONS.find((section) => section.id === activeSection) ??
    ADMIN_SECTIONS[0];

  /** 切换业务区并关闭移动端抽屉，副作用是触发父级导航回调。 */
  const navigateTo = (sectionId) => {
    onNavigate(sectionId);
    setDrawerOpen(false);
  };

  /** 触发返回站点行为；未提供回调时复用导航回调通知父级。 */
  const returnToSite = () => {
    if (onReturnToSite) {
      onReturnToSite();
      return;
    }

    onNavigate("site");
  };

  return (
    <div className={`admin-shell${drawerOpen ? " is-drawer-open" : ""}`}>
      <aside className="admin-shell__sidebar" aria-label="后台主导航">
        <div className="admin-shell__brand">
          <img
            className="admin-shell__brand-mark"
            src="/logo-lines-mark.png"
            alt="平行线"
          />
          <div className="admin-shell__brand-copy">
            <strong>平行线后台</strong>
          </div>
          <button
            className="admin-shell__drawer-close"
            type="button"
            aria-label="关闭导航"
            onClick={() => setDrawerOpen(false)}
          >
            <CloseOutlined />
          </button>
        </div>

        <nav className="admin-shell__nav">
          {ADMIN_SECTIONS.map((section) => (
            <button
              className={`admin-shell__nav-item${
                section.id === activeItem.id ? " is-active" : ""
              }`}
              type="button"
              key={section.id}
              aria-current={section.id === activeItem.id ? "page" : undefined}
              onClick={() => navigateTo(section.id)}
            >
              <span className="admin-shell__nav-icon" aria-hidden="true">
                {section.icon}
              </span>
              <span>{section.label}</span>
            </button>
          ))}
        </nav>

        <div className="admin-shell__sidebar-footer">
          <button
            className="admin-shell__return"
            type="button"
            onClick={returnToSite}
          >
            <ExportOutlined aria-hidden="true" />
            <span>返回站点</span>
          </button>

          <div className="admin-shell__admin-card">
            <span className="admin-shell__avatar" aria-hidden="true">
              <UserOutlined />
            </span>
            <span className="admin-shell__admin-copy">
              <strong>{adminName}</strong>
              <small>{adminRole}</small>
            </span>
            <DownOutlined className="admin-shell__admin-chevron" aria-hidden="true" />
          </div>
        </div>
      </aside>

      <button
        className="admin-shell__scrim"
        type="button"
        aria-label="关闭导航"
        tabIndex={drawerOpen ? 0 : -1}
        onClick={() => setDrawerOpen(false)}
      />

      <div className="admin-shell__workspace">
        <header className="admin-shell__topbar">
          <div className="admin-shell__topbar-start">
            <button
              className="admin-shell__menu-button"
              type="button"
              aria-label="打开导航"
              aria-expanded={drawerOpen}
              onClick={() => setDrawerOpen(true)}
            >
              <MenuOutlined />
            </button>

            <div className="admin-shell__mobile-brand" aria-hidden="true">
              <img src="/logo-lines-mark.png" alt="" />
              <strong>平行线后台</strong>
            </div>

            <div className="admin-shell__breadcrumb" aria-label="面包屑">
              <span>运营控制台</span>
              <span aria-hidden="true">/</span>
              <strong>{activeItem.label}</strong>
            </div>
          </div>

          <div className="admin-shell__topbar-actions">
            <button
              className="admin-shell__icon-button"
              type="button"
              aria-label={`通知，${notificationCount} 条未读`}
            >
              <BellOutlined />
              {notificationCount > 0 ? (
                <span className="admin-shell__notification-count">
                  {notificationCount > 99 ? "99+" : notificationCount}
                </span>
              ) : null}
            </button>

            <div className="admin-shell__topbar-user">
              <span className="admin-shell__avatar admin-shell__avatar--small" aria-hidden="true">
                <UserOutlined />
              </span>
              <span>{adminName}</span>
              <DownOutlined aria-hidden="true" />
            </div>
          </div>
        </header>

        <main className="admin-shell__content">{children}</main>
      </div>

      <nav className="admin-shell__bottom-nav" aria-label="移动端主导航">
        {ADMIN_SECTIONS.map((section) => (
          <button
            className={`admin-shell__bottom-item${
              section.id === activeItem.id ? " is-active" : ""
            }`}
            type="button"
            key={section.id}
            aria-current={section.id === activeItem.id ? "page" : undefined}
            onClick={() => navigateTo(section.id)}
          >
            <span aria-hidden="true">{section.icon}</span>
            <small>{section.mobileLabel}</small>
          </button>
        ))}
      </nav>
    </div>
  );
}

export { ADMIN_SECTIONS };
