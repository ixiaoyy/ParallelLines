import { useRef, useState } from "react";
import {
  ArrowLeftOutlined,
  CheckCircleFilled,
  ClockCircleOutlined,
  MailOutlined,
  MoreOutlined,
  SafetyCertificateOutlined,
  SaveOutlined,
  SearchOutlined,
  TeamOutlined,
  TrophyOutlined,
  UserOutlined,
} from "@ant-design/icons";
import "./AdminPages.css";

const userRecords = [
  {
    id: "u-01",
    name: "小小鸡仔",
    email: "xiaoxiao-jizai@pingxingxian.space",
    role: "用户",
    status: "正常",
    badge: "马甲账号",
    topics: 9,
    replies: 9,
    growth: 30,
    points: 30,
    trust: "TL1 · 基础成员",
    joined: "2026/06/23",
    active: "昨天 21:34",
    initials: "鸡",
  },
  {
    id: "u-02",
    name: "小小快讯",
    email: "xiaoxiao-news@pingxingxian.space",
    role: "用户",
    status: "正常",
    badge: "马甲账号",
    topics: 16,
    replies: 5,
    growth: 48,
    points: 76,
    trust: "TL1 · 基础成员",
    joined: "2026/06/18",
    active: "今天 10:12",
    initials: "讯",
  },
  {
    id: "u-03",
    name: "林屿",
    email: "linyu@example.com",
    role: "用户",
    status: "正常",
    badge: "真实用户",
    topics: 4,
    replies: 27,
    growth: 84,
    points: 120,
    trust: "TL2 · 成员",
    joined: "2026/06/29",
    active: "今天 09:48",
    initials: "林",
  },
  {
    id: "u-04",
    name: "frontier_bot_0623153909",
    email: "frontier-bot-0623153909@example.com",
    role: "用户",
    status: "待验证",
    badge: "真实用户",
    topics: 0,
    replies: 0,
    growth: 0,
    points: 0,
    trust: "TL0 · 新成员",
    joined: "2026/07/08",
    active: "2 天前",
    initials: "F",
  },
  {
    id: "u-05",
    name: "administrator",
    email: "admin@pingxingxian.space",
    role: "超级管理员",
    status: "正常",
    badge: "站点团队",
    topics: 21,
    replies: 63,
    growth: 260,
    points: 1024,
    trust: "TL4 · 领袖",
    joined: "2026/05/01",
    active: "刚刚",
    initials: "A",
  },
];

/**
 * 提供可搜索、筛选和切换详情的用户管理原型；保存反馈仅影响当前页面会话。
 * 该组件没有外部副作用，也不会向真实接口提交用户资料。
 */
export function UsersPage() {
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedId, setSelectedId] = useState(userRecords[0].id);
  const [mobileDetail, setMobileDetail] = useState(false);
  const [saved, setSaved] = useState(false);
  const listScrollTopRef = useRef(0);

  const normalizedQuery = query.trim().toLowerCase();
  const visibleUsers = userRecords.filter((user) => {
    const matchesQuery = !normalizedQuery || `${user.name} ${user.email}`.toLowerCase().includes(normalizedQuery);
    const matchesRole = roleFilter === "all" || user.role === roleFilter;
    const matchesStatus = statusFilter === "all" || user.status === statusFilter;
    return matchesQuery && matchesRole && matchesStatus;
  });
  const activeUserId = visibleUsers.some((user) => user.id === selectedId)
    ? selectedId
    : visibleUsers[0]?.id;
  const selectedUser = visibleUsers.find((user) => user.id === activeUserId) ?? userRecords[0];

  /**
   * Applies a user-list filter and exits compact detail mode so hidden accounts cannot be edited.
   * @param {(value: string) => void} setFilter State setter for the changed filter.
   * @param {string} value New filter value.
   * @returns {void} Updates the selected filter and local compact-pane feedback state.
   */
  function handleFilterChange(setFilter, value) {
    setFilter(value);
    setMobileDetail(false);
    setSaved(false);
  }

  /**
   * Opens one account in the compact single-pane layout and starts its detail at the top.
   * @param {string} userId Account id selected from the visible list.
   * @returns {void} Updates local selection and, on compact screens, stores/restores document scroll state.
   */
  function handleOpenUserDetail(userId) {
    setSelectedId(userId);
    setMobileDetail(true);
    setSaved(false);

    if (window.matchMedia("(max-width: 920px)").matches) {
      listScrollTopRef.current = window.scrollY;
      window.requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "auto" }));
    }
  }

  /**
   * Returns from the compact detail pane to the exact list position the administrator left.
   * @returns {void} Hides the detail pane and restores the previous document scroll offset on compact screens.
   */
  function handleCloseUserDetail() {
    setMobileDetail(false);
    if (window.matchMedia("(max-width: 920px)").matches) {
      window.requestAnimationFrame(() => window.scrollTo({ top: listScrollTopRef.current, behavior: "auto" }));
    }
  }

  return (
    <div className={`admin-page users-page${mobileDetail ? " is-showing-detail" : ""}${visibleUsers.length === 0 ? " is-empty" : ""}`}>
      <header className="admin-page__header">
        <div>
          <p className="admin-page__eyebrow">账号与权限</p>
          <h1>用户管理</h1>
          <p>查找账号、调整权限，并查看用户在社区中的成长情况。</p>
        </div>
        <div className="admin-page__header-stat">
          <span>全部用户</span>
          <strong>1,286</strong>
          <small>真实用户 1,247</small>
        </div>
      </header>

      <div className="users-toolbar" aria-label="用户筛选">
        <label className="admin-search-field">
          <SearchOutlined aria-hidden="true" />
          <span className="sr-only">搜索用户</span>
          <input
            type="search"
            value={query}
            onChange={(event) => handleFilterChange(setQuery, event.target.value)}
            placeholder="搜索用户名或邮箱"
          />
        </label>
        <label className="admin-select-field">
          <span>角色</span>
          <select value={roleFilter} onChange={(event) => handleFilterChange(setRoleFilter, event.target.value)}>
            <option value="all">全部角色</option>
            <option value="用户">用户</option>
            <option value="超级管理员">超级管理员</option>
          </select>
        </label>
        <label className="admin-select-field">
          <span>状态</span>
          <select value={statusFilter} onChange={(event) => handleFilterChange(setStatusFilter, event.target.value)}>
            <option value="all">全部状态</option>
            <option value="正常">正常</option>
            <option value="待验证">待验证</option>
          </select>
        </label>
        <span className="users-toolbar__result">找到 {visibleUsers.length} 位用户</span>
      </div>

      <div className="users-master-detail">
        <section className="users-list-pane" aria-label="用户列表">
          <div className="users-pane-heading">
            <span>用户</span>
            <span>最近活跃</span>
          </div>
          <div className="users-list">
            {visibleUsers.length > 0 ? visibleUsers.map((user) => (
              <button
                type="button"
                key={user.id}
                className={`users-list-item${activeUserId === user.id ? " is-active" : ""}`}
                aria-pressed={activeUserId === user.id}
                onClick={() => handleOpenUserDetail(user.id)}
              >
                <span className="user-avatar" aria-hidden="true">{user.initials}</span>
                <span className="users-list-item__identity">
                  <strong>{user.name}</strong>
                  <small>{user.email}</small>
                  <span className="users-list-item__tags">
                    <em>{user.role}</em>
                    {user.badge === "马甲账号" && <em className="is-persona">马甲</em>}
                  </span>
                </span>
                <span className="users-list-item__activity">
                  <time>{user.active}</time>
                  <small className={user.status === "正常" ? "is-success" : "is-warning"}>{user.status}</small>
                </span>
              </button>
            )) : (
              <div className="admin-empty-state">
                <TeamOutlined aria-hidden="true" />
                <strong>没有匹配的用户</strong>
                <span>尝试修改关键词或筛选条件。</span>
              </div>
            )}
          </div>
        </section>

        <section className="users-detail-pane" aria-label={`${selectedUser.name} 的用户详情`}>
          <button type="button" className="users-mobile-back" onClick={handleCloseUserDetail}>
            <ArrowLeftOutlined aria-hidden="true" /> 返回用户列表
          </button>

          <div className="user-detail-header">
            <span className="user-avatar is-large" aria-hidden="true">{selectedUser.initials}</span>
            <div className="user-detail-header__identity">
              <div>
                <h2>{selectedUser.name}</h2>
                <span className={`admin-status-pill${selectedUser.status === "正常" ? " is-success" : " is-warning"}`}>
                  {selectedUser.status === "正常" && <CheckCircleFilled aria-hidden="true" />}
                  {selectedUser.status}
                </span>
              </div>
              <p><MailOutlined aria-hidden="true" /> {selectedUser.email}</p>
              <span>{selectedUser.badge} · 注册于 {selectedUser.joined}</span>
            </div>
            <button type="button" className="admin-icon-button" aria-label="更多用户操作"><MoreOutlined /></button>
          </div>

          <div className="user-stat-strip" aria-label="用户社区数据">
            <div><span>内容贡献</span><strong>{selectedUser.topics} 主题 / {selectedUser.replies} 回复</strong></div>
            <div><span>成长值</span><strong>{selectedUser.growth}</strong></div>
            <div><span>信任等级</span><strong>{selectedUser.trust}</strong></div>
            <div><span>可用积分</span><strong>{selectedUser.points}</strong></div>
          </div>

          <div className="user-edit-section">
            <div className="user-edit-section__heading">
              <SafetyCertificateOutlined aria-hidden="true" />
              <div><h3>账号权限</h3><p>调整该用户可访问的后台与社区能力。</p></div>
            </div>
            <div className="admin-form-grid">
              <label><span>角色</span><select defaultValue={selectedUser.role}><option>用户</option><option>版主</option><option>管理员</option><option>超级管理员</option></select></label>
              <label><span>账号状态</span><select defaultValue={selectedUser.status}><option>正常</option><option>待验证</option><option>停用</option></select></label>
              <label><span>等级</span><input type="number" defaultValue={selectedUser.trust.slice(2, 3)} min="0" max="4" /></label>
            </div>
          </div>

          <div className="user-edit-section">
            <div className="user-edit-section__heading">
              <TrophyOutlined aria-hidden="true" />
              <div><h3>积分与成长</h3><p>用于社区激励与信任体系，不影响账号权限。</p></div>
            </div>
            <div className="admin-form-grid is-two-column">
              <label><span>成长值</span><input type="number" defaultValue={selectedUser.growth} min="0" /></label>
              <label><span>可用积分</span><input type="number" defaultValue={selectedUser.points} min="0" /></label>
            </div>
          </div>

          <footer className="user-detail-actions" aria-live="polite">
            {saved && <span className="admin-inline-success"><CheckCircleFilled aria-hidden="true" /> 更改已保存</span>}
            <button type="button" className="admin-primary-button" onClick={() => setSaved(true)}>
              <SaveOutlined aria-hidden="true" /> 保存更改
            </button>
          </footer>
        </section>
      </div>
    </div>
  );
}

export default UsersPage;
