import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Plus, Ticket, House, Crown, Wrench, ArrowRight, Users, Trash, ShieldCheck, Spinner } from "@phosphor-icons/react";
import { motion } from "framer-motion";
import api, { formatApiErrorDetail } from "../lib/api";
import { useAuth, ROLE_LABELS } from "../context/AuthContext";
import { AppShell } from "../components/AppShell";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const ROLE_COLORS = { super_admin: "#EF4444", moderator: "#F59E0B", installer: "#3B82F6", client: "#10B981", guest: "#A1A1AA" };

function UsersManager() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const canManage = user.role === "super_admin";

  const load = useCallback(async () => setUsers(await api.listUsers()), []);
  useEffect(() => { load(); }, [load]);

  const changeRole = async (id, role) => {
    await api.updateUserRole(id, role);
    toast.success("Rôle mis à jour");
    load();
  };
  const remove = async (id) => {
    try { await api.deleteUser(id); toast.success("Utilisateur supprimé"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <div className="border border-border/60 bg-[#121212] rounded-lg">
      <div className="p-6 border-b border-border/50">
        <p className="overline text-zinc-500">Administration</p>
        <h2 className="font-display text-2xl font-bold tracking-tight mt-1">Tous les utilisateurs ({users.length})</h2>
      </div>
      <div className="divide-y divide-border/40">
        {users.map((u) => (
          <div key={u.id} data-testid={`user-row-${u.id}`} className="flex items-center justify-between p-4 md:px-6 gap-4">
            <div className="min-w-0">
              <p className="font-medium text-sm truncate">{u.name}</p>
              <p className="text-xs text-zinc-500 truncate">{u.email}</p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {canManage ? (
                <Select value={u.role} onValueChange={(v) => changeRole(u.id, v)}>
                  <SelectTrigger data-testid={`role-select-${u.id}`} className="w-[150px] h-9 bg-black/40 border-border/70 rounded-full text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.keys(ROLE_LABELS).map((r) => (
                      <SelectItem key={r} value={r}>{ROLE_LABELS[r]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <span className="text-xs px-2.5 py-1 rounded-full" style={{ background: `${ROLE_COLORS[u.role]}22`, color: ROLE_COLORS[u.role] }}>
                  {ROLE_LABELS[u.role]}
                </span>
              )}
              {canManage && u.id !== user.id && (
                <button data-testid={`delete-user-${u.id}`} onClick={() => remove(u.id)} className="text-zinc-500 hover:text-offline transition-colors duration-200">
                  <Trash size={16} />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Home() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [installations, setInstallations] = useState(null);
  const [tab, setTab] = useState("installations");
  const [newName, setNewName] = useState("");
  const [code, setCode] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [joinOpen, setJoinOpen] = useState(false);

  const canCreate = user.role === "super_admin" || user.role === "installer";
  const isAdminView = user.role === "super_admin" || user.role === "moderator";

  const load = useCallback(async () => setInstallations(await api.listInstallations()), []);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!newName.trim()) return;
    const inst = await api.createInstallation(newName.trim());
    toast.success("Installation créée");
    setCreateOpen(false); setNewName("");
    navigate(`/installations/${inst.id}`);
  };

  const join = async () => {
    try {
      const res = await api.acceptInvite(code.trim());
      toast.success(res.role === "client" ? "Vous êtes maintenant maître de l'équipement" : "Invitation acceptée");
      setJoinOpen(false); setCode("");
      await load();
      navigate(`/installations/${res.installation.id}`);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const headerRight = (
    <span className="hidden sm:inline text-xs px-2.5 py-1 rounded-full" style={{ background: `${ROLE_COLORS[user.role]}22`, color: ROLE_COLORS[user.role] }}>
      {ROLE_LABELS[user.role]}
    </span>
  );

  return (
    <AppShell right={headerRight}>
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-8">
        <div>
          <p className="overline text-zinc-500">Bienvenue, {user.name}</p>
          <h1 className="font-display text-4xl md:text-5xl font-extrabold tracking-tighter mt-1">
            {isAdminView ? "Console d'administration" : "Mes installations"}
          </h1>
        </div>
        <div className="flex flex-wrap gap-3">
          <Dialog open={joinOpen} onOpenChange={setJoinOpen}>
            <DialogTrigger asChild>
              <Button data-testid="join-btn" variant="outline" className="rounded-full border-border/70 font-semibold">
                <Ticket weight="bold" size={16} className="mr-2" /> Rejoindre avec un code
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-[#121212] border-border/70">
              <DialogHeader><DialogTitle className="font-display tracking-tight">Rejoindre une installation</DialogTitle></DialogHeader>
              <div className="py-2">
                <Label className="text-xs text-zinc-400">Code d'invitation</Label>
                <Input data-testid="join-code-input" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="EX: A1B2C3D4" className="mt-1 bg-black/40 border-border/70 font-mono-num tracking-widest uppercase" />
              </div>
              <DialogFooter>
                <Button data-testid="join-submit-btn" onClick={join} className="rounded-full bg-heat text-black hover:bg-heat-soft font-semibold">Rejoindre</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {canCreate && (
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger asChild>
                <Button data-testid="create-installation-btn" className="rounded-full bg-heat text-black hover:bg-heat-soft font-semibold">
                  <Plus weight="bold" size={16} className="mr-2" /> Nouvelle installation
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-[#121212] border-border/70">
                <DialogHeader><DialogTitle className="font-display tracking-tight">Nouvelle installation</DialogTitle></DialogHeader>
                <div className="py-2">
                  <Label className="text-xs text-zinc-400">Nom de l'installation</Label>
                  <Input data-testid="installation-name-input" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Ex : Maison Dupont" className="mt-1 bg-black/40 border-border/70" />
                </div>
                <DialogFooter>
                  <Button data-testid="create-submit-btn" onClick={create} className="rounded-full bg-heat text-black hover:bg-heat-soft font-semibold">Créer</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {isAdminView && (
        <div className="flex gap-1 border border-border/60 bg-[#121212] rounded-full p-1 w-fit mb-6">
          {[["installations", "Installations", House], ["users", "Utilisateurs", Users]].map(([k, l, Icon]) => (
            <button key={k} data-testid={`admintab-${k}`} onClick={() => setTab(k)}
              className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-colors duration-200"
              style={{ background: tab === k ? "#FAFAFA" : "transparent", color: tab === k ? "#0A0A0A" : "#A1A1AA" }}>
              <Icon weight={tab === k ? "fill" : "regular"} size={17} /> {l}
            </button>
          ))}
        </div>
      )}

      {(!isAdminView || tab === "installations") && (
        <div data-testid="installations-grid" className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
          {installations === null && (
            <div className="col-span-full flex items-center gap-3 text-zinc-500 py-10">
              <Spinner size={20} className="animate-spin text-heat" /> Chargement des installations…
            </div>
          )}
          {installations !== null && installations.length === 0 && (
            <p className="text-zinc-500 text-sm col-span-full py-10">
              Aucune installation pour l'instant. {canCreate ? "Créez-en une." : "Rejoignez-en une avec un code d'invitation."}
            </p>
          )}
          {(installations || []).map((inst, i) => (
            <motion.button
              key={inst.id}
              initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              data-testid={`installation-card-${inst.id}`}
              onClick={() => navigate(`/installations/${inst.id}`)}
              className="text-left border border-border/60 bg-[#121212] rounded-lg p-6 hover:border-zinc-500 transition-colors duration-200 group"
            >
              <div className="flex items-start justify-between">
                <div className="w-11 h-11 rounded-md bg-heat/15 border border-heat/30 flex items-center justify-center">
                  <House weight="duotone" size={24} className="text-heat" />
                </div>
                <ArrowRight size={18} className="text-zinc-600 group-hover:text-white transition-colors duration-200" />
              </div>
              <h3 className="font-display text-xl font-bold tracking-tight mt-4">{inst.name}</h3>
              <div className="flex flex-col gap-1 mt-3 text-xs text-zinc-500">
                <span className="flex items-center gap-1.5"><Crown size={13} className="text-amber-400" /> {inst.owner_name || "Sans propriétaire"}</span>
                <span className="flex items-center gap-1.5"><Wrench size={13} className="text-cool" /> {inst.installer_name || "—"}</span>
              </div>
              <span className="inline-block mt-4 text-[10px] px-2 py-0.5 rounded-full" style={{ background: inst.can_write ? "rgba(16,185,129,0.12)" : "rgba(161,161,170,0.12)", color: inst.can_write ? "#10B981" : "#A1A1AA" }}>
                {inst.can_write ? "Contrôle actif" : "Lecture seule"}
              </span>
            </motion.button>
          ))}
        </div>
      )}

      {isAdminView && tab === "users" && <UsersManager />}
    </AppShell>
  );
}
