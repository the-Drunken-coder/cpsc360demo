import { Button, Menu, MenuDivider, MenuItem, Popover, Tag } from "@blueprintjs/core";
import type { Role } from "../api/types";
import { useSession } from "../session/SessionProvider";
import { toastError } from "./toaster";

const ROLE_INTENT: Record<Role, "primary" | "success" | "none"> = { analyst: "primary", lead: "success", viewer: "none" };

export function UserSwitcher() {
  const { user, users, switchUser } = useSession();
  return (
    <Popover placement="bottom-end" minimal content={
      <Menu>
        <MenuDivider title="Demo users (prototype auth)" />
        {users.map((u) => (
          <MenuItem key={u.id} text={u.display_name} active={u.id === user.id}
            label={u.role} icon={u.role === "viewer" ? "eye-open" : "person"}
            onClick={() => { if (u.id !== user.id) switchUser(u.handle).catch(toastError); }} />
        ))}
      </Menu>
    }>
      <Button minimal icon="person" rightIcon="caret-down" className="user-switcher">
        {user.display_name} <Tag minimal intent={ROLE_INTENT[user.role]}>{user.role}</Tag>
      </Button>
    </Popover>
  );
}
