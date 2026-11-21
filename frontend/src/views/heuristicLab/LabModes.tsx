import { Classes } from "@blueprintjs/core";
import { NavLink, useLocation } from "react-router-dom";

export const LAB_PATH = "/heuristic-lab";
export const REPLAY_PATH = `${LAB_PATH}/replay`;

/** Switches between the batch comparison and the replay. */
export function LabModes() {
  const replay = useLocation().pathname.startsWith(REPLAY_PATH);
  const modes = [
    { to: LAB_PATH, label: "Compare", icon: "comparison", active: !replay },
    { to: REPLAY_PATH, label: "Replay", icon: "play", active: replay },
  ];
  return <nav className={`${Classes.BUTTON_GROUP} lab-modes`} aria-label="Lab mode">
    {modes.map((mode) => <NavLink key={mode.to} to={mode.to} aria-current={mode.active ? "page" : undefined}
      className={`${Classes.BUTTON} ${Classes.SMALL} ${mode.active ? Classes.ACTIVE : ""}`}>
      <span className={`${Classes.ICON} bp5-icon-${mode.icon}`} />
      <span className={Classes.BUTTON_TEXT}>{mode.label}</span>
    </NavLink>)}
  </nav>;
}
