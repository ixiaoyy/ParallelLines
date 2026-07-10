import { useEffect, useRef, useState } from "react";
import { AdminShell, ADMIN_SECTIONS } from "./components/AdminShell.jsx";
import AnalyticsPage from "./pages/AnalyticsPage.jsx";
import ModerationPage from "./pages/ModerationPage.jsx";
import SystemPage from "./pages/SystemPage.jsx";
import UsersPage from "./pages/UsersPage.jsx";
import WorkbenchPage from "./pages/WorkbenchPage.jsx";
import "./App.css";

const VALID_SECTIONS = new Set(ADMIN_SECTIONS.map((section) => section.id));

/**
 * Reads the prototype section encoded in the URL hash.
 * @returns {string} A valid admin section id, defaulting to analytics.
 */
function readSectionFromHash() {
  const requestedSection = window.location.hash.replace(/^#\/?/, "");
  return VALID_SECTIONS.has(requestedSection) ? requestedSection : "analytics";
}

/**
 * Renders the selected clickable admin redesign prototype.
 * @returns {React.ReactElement} The shared admin shell and active page.
 */
export function App() {
  const [activeSection, setActiveSection] = useState(readSectionFromHash);
  const [notice, setNotice] = useState("");
  const noticeTimerRef = useRef(null);

  useEffect(() => {
    /** Keeps browser back/forward navigation synchronized with the prototype. */
    const syncSectionFromHash = () => setActiveSection(readSectionFromHash());
    window.addEventListener("hashchange", syncSectionFromHash);
    return () => window.removeEventListener("hashchange", syncSectionFromHash);
  }, []);

  useEffect(
    () => () => {
      if (noticeTimerRef.current) window.clearTimeout(noticeTimerRef.current);
    },
    [],
  );

  /**
   * Changes the visible admin workspace and records it in the URL hash.
   * @param {string} sectionId Target admin section id.
   * @returns {void}
   */
  function handleNavigate(sectionId) {
    if (!VALID_SECTIONS.has(sectionId)) return;
    setActiveSection(sectionId);
    window.location.hash = `/${sectionId}`;
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: prefersReducedMotion ? "auto" : "smooth" });
  }

  /**
   * Explains the return-site affordance without leaving the standalone design prototype.
   * @returns {void}
   */
  function handleReturnToSite() {
    setNotice("这是独立设计原型；正式实现后会返回平行线主站。");
    if (noticeTimerRef.current) window.clearTimeout(noticeTimerRef.current);
    noticeTimerRef.current = window.setTimeout(() => setNotice(""), 2600);
  }

  /**
   * Chooses the active prototype page while preserving a single shared shell.
   * @returns {React.ReactElement} The current admin page.
   */
  function renderActivePage() {
    switch (activeSection) {
      case "dashboard":
        return <WorkbenchPage onNavigate={handleNavigate} />;
      case "users":
        return <UsersPage />;
      case "moderation":
        return <ModerationPage />;
      case "system":
        return <SystemPage />;
      case "analytics":
      default:
        return <AnalyticsPage />;
    }
  }

  return (
    <AdminShell
      activeSection={activeSection}
      onNavigate={handleNavigate}
      onReturnToSite={handleReturnToSite}
    >
      {renderActivePage()}
      <div className={`prototype-notice${notice ? " is-visible" : ""}`} role="status">
        {notice}
      </div>
    </AdminShell>
  );
}
