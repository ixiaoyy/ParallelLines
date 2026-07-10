import { useState } from "react";
import {
  ArrowLeftOutlined,
  CheckCircleFilled,
  CheckOutlined,
  ClockCircleOutlined,
  CloseOutlined,
  CommentOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
  FlagOutlined,
  InboxOutlined,
  LinkOutlined,
  SafetyCertificateOutlined,
  UserOutlined,
} from "@ant-design/icons";
import "./AdminPages.css";

const moderationQueues = {
  topics: [
    {
      id: "topic-2418",
      title: "如何看待最近的 AI 编程工具变化？",
      excerpt: "最近试用了几款新的编程工具，感觉从补全代码逐渐走向了完整任务协作……",
      author: "林屿",
      board: "前沿观察",
      submitted: "12 分钟前",
      wait: "正常",
      reason: "新用户首帖",
      content: "最近试用了几款新的编程工具，感觉它们已经从简单补全代码逐渐走向了完整任务协作。真正值得讨论的可能不是它们能写多少代码，而是团队如何建立新的评审边界。想听听大家最近的使用体验，以及你们会怎样判断生成内容是否可靠。",
    },
    {
      id: "topic-2417",
      title: "整理了一份低代码平台选型笔记",
      excerpt: "从权限、扩展性、部署方式三个维度比较了目前常见方案，欢迎补充……",
      author: "夏弥",
      board: "资源分享",
      submitted: "28 分钟前",
      wait: "正常",
      reason: "包含外部链接",
      content: "这份笔记主要从权限模型、扩展方式和部署成本三个维度整理。文末包含官方文档链接，没有推广或付费引流内容。欢迎有实际落地经验的朋友补充踩坑记录。",
    },
    {
      id: "topic-2415",
      title: "请问帖子发布后还能修改标签吗？",
      excerpt: "第一次发帖时选错了标签，现在找不到修改入口……",
      author: "昼川",
      board: "问答求助",
      submitted: "1 小时前",
      wait: "即将超时",
      reason: "新用户首帖",
      content: "第一次发帖时选错了标签，现在找不到修改入口。请问发布后多久内可以自行修改？如果不能修改，应该联系哪位版主协助处理？",
    },
  ],
  replies: [
    {
      id: "reply-8802",
      title: "回复：整理了一份低代码平台选型笔记",
      excerpt: "我们团队去年落地过类似方案，权限同步是最容易被低估的部分……",
      author: "江序",
      board: "资源分享",
      submitted: "8 分钟前",
      wait: "正常",
      reason: "新用户回复",
      content: "我们团队去年落地过类似方案，权限同步是最容易被低估的部分。建议在选型阶段就验证组织架构变更后的回收路径，不要只看首次同步是否成功。",
    },
    {
      id: "reply-8796",
      title: "回复：你最近读完了哪本书？",
      excerpt: "推荐《始于极限》，其中关于日常选择的讨论很有启发……",
      author: "未眠",
      board: "读书会",
      submitted: "46 分钟前",
      wait: "正常",
      reason: "敏感词复核",
      content: "推荐《始于极限》，其中关于日常选择的讨论很有启发。作者不是给出标准答案，而是不断追问我们为什么会接受那些习以为常的边界。",
    },
  ],
  reports: [
    {
      id: "report-0710-018",
      title: "举报：回复中疑似包含人身攻击",
      excerpt: "举报人认为该回复针对发帖者本人，而不是讨论观点……",
      author: "青禾",
      board: "闲聊广场",
      submitted: "1 小时 48 分前",
      wait: "即将超时",
      reason: "言语攻击",
      content: "你根本没有理解这个问题，就不要用这种语气教育别人。先把最基础的背景搞清楚再来讨论吧。",
    },
    {
      id: "report-0710-017",
      title: "举报：主题中包含推广链接",
      excerpt: "正文多次引导用户前往站外页面注册，疑似营销内容……",
      author: "系统用户 1208",
      board: "资源分享",
      submitted: "52 分钟前",
      wait: "正常",
      reason: "广告推广",
      content: "这个工具最近开放了注册，使用我的邀请链接可以获得额外额度。更多介绍和优惠信息请访问站外页面。",
    },
    {
      id: "report-0710-015",
      title: "举报：重复发布相同内容",
      excerpt: "同一用户在三个版块发布了高度重复的主题……",
      author: "小径",
      board: "社区反馈",
      submitted: "2 小时前",
      wait: "正常",
      reason: "重复内容",
      content: "该用户在前沿观察、资源分享和闲聊广场连续发布相同正文，仅修改了标题。建议保留最相关版块的一条。",
    },
  ],
};

const moderationTabs = [
  { key: "topics", label: "待审主题", count: 8, icon: FileTextOutlined },
  { key: "replies", label: "待审回复", count: 4, icon: CommentOutlined },
  { key: "reports", label: "用户举报", count: 3, icon: FlagOutlined },
];

/**
 * 展示内容审核工作台，支持队列切换、选择条目和原型级通过/退回反馈。
 * 所有处理结果仅保存在当前组件状态，不会修改真实内容。
 */
export function ModerationPage() {
  const [activeTab, setActiveTab] = useState("topics");
  const [selectedId, setSelectedId] = useState(moderationQueues.topics[0].id);
  const [mobileReview, setMobileReview] = useState(false);
  const [result, setResult] = useState(null);
  const activeItems = moderationQueues[activeTab];
  const selectedItem = activeItems.find((item) => item.id === selectedId) ?? activeItems[0];
  const isReport = activeTab === "reports";

  return (
    <div className={`admin-page moderation-page${mobileReview ? " is-reviewing" : ""}`}>
      <header className="admin-page__header">
        <div>
          <p className="admin-page__eyebrow">社区治理</p>
          <h1>内容审核</h1>
          <p>按提交顺序检查主题、回复和举报，优先处理即将超时的内容。</p>
        </div>
        <div className="admin-page__header-stat is-warning">
          <span>今日待处理</span>
          <strong>15</strong>
          <small>1 项即将超时</small>
        </div>
      </header>

      <nav className="admin-tabs" aria-label="审核队列类型">
        {moderationTabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              type="button"
              key={tab.key}
              className={activeTab === tab.key ? "is-active" : ""}
              aria-current={activeTab === tab.key ? "page" : undefined}
              onClick={() => {
                setActiveTab(tab.key);
                setSelectedId(moderationQueues[tab.key][0].id);
                setMobileReview(false);
                setResult(null);
              }}
            >
              <Icon aria-hidden="true" />
              <span>{tab.label}</span>
              <em>{tab.count}</em>
            </button>
          );
        })}
      </nav>

      <div className="moderation-workspace">
        <section className="moderation-queue" aria-label="待处理队列">
          <div className="moderation-queue__heading">
            <div><strong>等待处理</strong><span>按提交时间排序</span></div>
            <label>
              <span className="sr-only">队列排序</span>
              <select defaultValue="oldest"><option value="oldest">最早提交</option><option value="newest">最新提交</option></select>
            </label>
          </div>
          <div className="moderation-queue__list">
            {activeItems.map((item) => (
              <button
                type="button"
                key={item.id}
                className={`moderation-queue-item${selectedItem.id === item.id ? " is-active" : ""}`}
                aria-pressed={selectedItem.id === item.id}
                onClick={() => {
                  setSelectedId(item.id);
                  setMobileReview(true);
                  setResult(null);
                }}
              >
                <span className="moderation-queue-item__topline">
                  <em className={item.wait === "即将超时" ? "is-urgent" : ""}>
                    <ClockCircleOutlined aria-hidden="true" /> {item.submitted}
                  </em>
                  <small>{item.board}</small>
                </span>
                <strong>{item.title}</strong>
                <p>{item.excerpt}</p>
                <span className="moderation-queue-item__meta"><UserOutlined aria-hidden="true" /> {item.author}<i>{item.reason}</i></span>
              </button>
            ))}
          </div>
          <footer className="moderation-queue__footer"><InboxOutlined aria-hidden="true" /> 当前显示 {activeItems.length} 项示例内容</footer>
        </section>

        <article className="moderation-review" aria-live="polite">
          <button type="button" className="moderation-mobile-back" onClick={() => setMobileReview(false)}>
            <ArrowLeftOutlined aria-hidden="true" /> 返回审核队列
          </button>

          {result && (
            <div className={`moderation-result is-${result.tone}`}>
              {result.tone === "success" ? <CheckCircleFilled aria-hidden="true" /> : <ExclamationCircleOutlined aria-hidden="true" />}
              <span><strong>{result.title}</strong><small>{result.detail}</small></span>
            </div>
          )}

          <header className="moderation-review__header">
            <div>
              <span className="admin-status-pill is-neutral"><SafetyCertificateOutlined aria-hidden="true" /> {selectedItem.reason}</span>
              <h2>{selectedItem.title}</h2>
              <p>{activeTab === "topics" ? "主题" : activeTab === "replies" ? "回复" : "举报内容"}编号 {selectedItem.id}</p>
            </div>
            <span className={`moderation-review__timer${selectedItem.wait === "即将超时" ? " is-urgent" : ""}`}>
              <ClockCircleOutlined aria-hidden="true" /> {selectedItem.submitted}
            </span>
          </header>

          <div className="moderation-review__meta">
            <div><span>提交用户</span><strong>{selectedItem.author}</strong></div>
            <div><span>所属版块</span><strong>{selectedItem.board}</strong></div>
            <div><span>触发原因</span><strong>{selectedItem.reason}</strong></div>
          </div>

          <section className="moderation-content-preview">
            <div className="moderation-content-preview__label">内容预览</div>
            <p>{selectedItem.content}</p>
            {selectedItem.reason === "包含外部链接" && (
              <span className="moderation-content-preview__link"><LinkOutlined aria-hidden="true" /> docs.example.com/platform-notes</span>
            )}
          </section>

          <section className="moderation-checklist">
            <h3>审核参考</h3>
            <div><CheckOutlined aria-hidden="true" /><span><strong>账号状态正常</strong><small>近期无处罚记录</small></span></div>
            <div><CheckOutlined aria-hidden="true" /><span><strong>内容未重复</strong><small>未发现站内高度相似内容</small></span></div>
            <div className={isReport ? "is-warning" : ""}>
              {isReport ? <ExclamationCircleOutlined aria-hidden="true" /> : <CheckOutlined aria-hidden="true" />}
              <span><strong>{isReport ? "需要人工判断语境" : "未命中高风险规则"}</strong><small>{isReport ? "系统无法确定是否构成违规" : "敏感词与推广风险检测通过"}</small></span>
            </div>
          </section>

          <footer className="moderation-actions">
            <button
              type="button"
              className="admin-secondary-button is-danger"
              onClick={() => setResult({ tone: "warning", title: isReport ? "内容已删除" : "内容已退回", detail: isReport ? "举报已结案，作者将收到站内通知。" : "已将修改原因发送给作者。" })}
            >
              <CloseOutlined aria-hidden="true" /> {isReport ? "删除内容" : "退回修改"}
            </button>
            <button
              type="button"
              className="admin-primary-button"
              onClick={() => setResult({ tone: "success", title: isReport ? "举报已忽略" : "审核已通过", detail: isReport ? "该举报已结案，原内容保持可见。" : "内容已进入对应版块。" })}
            >
              <CheckOutlined aria-hidden="true" /> {isReport ? "忽略举报" : "通过审核"}
            </button>
          </footer>
        </article>
      </div>
    </div>
  );
}

export default ModerationPage;
