import { SettingsView } from "./views/settings/SettingsView";
import { Alignment, Button, Classes, HotkeysProvider, Navbar, NavbarDivider, NavbarGroup, NavbarHeading, Tag } from "@blueprintjs/core";
import { useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { InvestigateProvider } from "./components/InvestigateProvider";
import { AppOmnibar } from "./components/AppOmnibar";
import { UserSwitcher } from "./components/UserSwitcher";
import { HotkeysHelp, useRegisteredHotkeys } from "./hotkeys/registry";
import { SelectionProvider } from "./session/SelectionProvider";
import { SessionProvider } from "./session/SessionProvider";
import { AnalyticsView } from "./views/analytics/AnalyticsView";
import { CompareView } from "./views/compare/CompareView";
import { ExplorerView } from "./views/explorer/ExplorerView";
import { IncidentView } from "./views/incident/IncidentView";
import { InvestigationView } from "./views/investigations/InvestigationView";
import { InvestigationsList } from "./views/investigations/InvestigationsList";
import { SourceView } from "./views/source/SourceView";
import { SelectionBadge } from "./components/SelectionBadge";
import { SourceStatusLine } from "./components/SourceStatusLine";

export function App() {
  return (
    <HotkeysProvider renderDialog={(state, { handleDialogClose }) => (
      state.isDialogOpen ? <HotkeysHelp active={state.hotkeys} onClose={handleDialogClose} /> : <></>
    )}>
      <div className="app">
        <div className="prototype-notice" role="note">
          Prototype · public SaferProducts.gov data only · not an official CPSC system · workspace changes are attributed and audited
        </div>
        <SessionProvider>
          <SelectionProvider>
            <InvestigateProvider>
              <Shell />
            </InvestigateProvider>
          </SelectionProvider>
        </SessionProvider>
      </div>
    </HotkeysProvider>
  );
}

const NAV = [
  { to: "/settings", label: "Settings", icon: "cog", end: false },
  { to: "/", label: "Explorer", icon: "search-template", end: true },
  { to: "/analytics", label: "Analytics", icon: "timeline-bar-chart", end: false },
  { to: "/investigations", label: "Investigations", icon: "folder-shared", end: false },
  { to: "/source", label: "Source", icon: "database", end: false },
] as const;

function Shell() {
  const [omnibarOpen, setOmnibarOpen] = useState(false);
  useRegisteredHotkeys({ omnibar: () => setOmnibarOpen(true) });
  return (
    <div className="shell">
      <Navbar className="app-navbar">
        <NavbarGroup align={Alignment.LEFT}>
          <NavbarHeading className="brand">CPSC<span>360</span></NavbarHeading>
          <NavbarDivider />
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
              className={({ isActive }) => `${Classes.BUTTON} ${Classes.MINIMAL} ${isActive ? Classes.ACTIVE : ""}`}>
              <span className={`${Classes.ICON} bp5-icon-${n.icon}`} />
              <span className={Classes.BUTTON_TEXT}>{n.label}</span>
            </NavLink>
          ))}
        </NavbarGroup>
        <NavbarGroup align={Alignment.RIGHT}>
          <SourceStatusLine />
          <NavbarDivider />
          <SelectionBadge />
          <Button minimal icon="search" onClick={() => setOmnibarOpen(true)} className="omnibar-trigger">
            Jump to… <Tag minimal className="kbd">Ctrl K</Tag>
          </Button>
          <NavbarDivider />
          <UserSwitcher />
        </NavbarGroup>
      </Navbar>
      <main className="main">
        <Routes>
          <Route path="/settings" element={<SettingsView />} />
          <Route path="/" element={<ExplorerView />} />
          <Route path="/incidents/:reportNo" element={<IncidentView />} />
          <Route path="/incidents/:reportNo/:tab" element={<IncidentView />} />
          <Route path="/compare" element={<CompareView />} />
          <Route path="/investigations" element={<InvestigationsList />} />
          <Route path="/investigations/:id" element={<InvestigationView />} />
          <Route path="/investigations/:id/:tab" element={<InvestigationView />} />
          <Route path="/analytics" element={<AnalyticsView />} />
          <Route path="/source" element={<SourceView />} />
        </Routes>
      </main>
      <AppOmnibar isOpen={omnibarOpen} onClose={() => setOmnibarOpen(false)} />
    </div>
  );
}
