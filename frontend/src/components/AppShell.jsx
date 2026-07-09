import { useState } from "react";
import { Thermometer, SignOut, UserCircle } from "@phosphor-icons/react";
import { useAuth, ROLE_LABELS } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

const ROLE_COLORS = {
  super_admin: "#EF4444",
  moderator: "#F59E0B",
  installer: "#3B82F6",
  client: "#10B981",
  guest: "#A1A1AA",
};

export const AppShell = ({ children, right }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const rc = ROLE_COLORS[user?.role] || "#A1A1AA";

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border/50 bg-black/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 md:px-8 h-16 flex items-center justify-between">
          <button onClick={() => navigate("/")} className="flex items-center gap-3" data-testid="logo-home">
            <div className="w-9 h-9 rounded-md bg-heat/15 border border-heat/30 flex items-center justify-center">
              <Thermometer weight="fill" size={20} className="text-heat" />
            </div>
            <div className="text-left">
              <p className="font-display font-extrabold tracking-tighter text-lg leading-none">ClimaZone</p>
              <p className="text-[10px] text-zinc-500 tracking-wider">GAINABLE CONNECTÉ</p>
            </div>
          </button>

          <div className="flex items-center gap-4">
            {right}
            <div className="relative">
              <button
                data-testid="user-menu-btn"
                onClick={() => setOpen((o) => !o)}
                className="flex items-center gap-2 rounded-full border border-border/70 pl-2 pr-3 py-1.5 hover:border-zinc-500 transition-colors duration-200"
              >
                <UserCircle weight="duotone" size={22} style={{ color: rc }} />
                <div className="text-left hidden sm:block">
                  <p className="text-xs font-semibold leading-none">{user?.name}</p>
                  <p className="text-[10px]" style={{ color: rc }}>{ROLE_LABELS[user?.role]}</p>
                </div>
              </button>
              {open && (
                <div className="absolute right-0 mt-2 w-56 rounded-lg border border-border/70 bg-[#121212] p-2 shadow-xl z-50">
                  <div className="px-3 py-2 border-b border-border/50 mb-1">
                    <p className="text-sm font-semibold">{user?.name}</p>
                    <p className="text-xs text-zinc-500">{user?.email}</p>
                    <span className="inline-block mt-1 text-[10px] px-2 py-0.5 rounded-full" style={{ background: `${rc}22`, color: rc }}>
                      {ROLE_LABELS[user?.role]}
                    </span>
                  </div>
                  <button
                    data-testid="logout-btn"
                    onClick={logout}
                    className="w-full flex items-center gap-2 rounded-md px-3 py-2 text-sm text-zinc-300 hover:bg-white/5 hover:text-white transition-colors duration-200"
                  >
                    <SignOut size={16} /> Se déconnecter
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 md:px-8 py-8">{children}</main>
    </div>
  );
};
