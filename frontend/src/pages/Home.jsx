import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Plus, Ticket, House, Crown, Wrench, ArrowRight, Users, Trash, ShieldCheck, Spinner, DownloadSimple, UploadSimple, FloppyDisk, PlugsConnected, QrCode } from "@phosphor-icons/react";
import { motion } from "framer-motion";
import api, { formatApiErrorDetail } from "../lib/api";
import { useAuth, ROLE_LABELS } from "../context/AuthContext";
import { AppShell } from "../components/AppShell";
import { CreateInstallationDialog } from "../components/CreateInstallationDialog";
import { TuyaManager } from "../components/TuyaManager";
import { CatalogManager } from "../components/CatalogManager";import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "../components/ui/alert-dialog";

const ROLE_COLORS = { super_admin: "#EF4444", moderator: "#F59E0B", installer: "#3B82F6", client: "#10B981", guest: "#71717A" };

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
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg">
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
                  <SelectTrigger data-testid={`role-select-${u.id}`} className="w-[150px] h-9 bg-zinc-100 border-border/70 rounded-full text-xs">
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

function BackupManager() {
  const [busy, setBusy] = useState("");
  const fileRef = useRef(null);

  const doDownload = async () => {
    setBusy("download");
    try {
      const data = await api.downloadBackup();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `zoneclimate-sauvegarde-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Sauvegarde téléchargée");
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setBusy(""); }
  };

  const doSaveNow = async () => {
    setBusy("save");
    try { await api.saveBackupNow(); toast.success("Sauvegarde enregistrée sur le serveur"); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setBusy(""); }
  };

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("restore");
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const res = await api.restoreBackup(data);
      const total = Object.values(res.counts || {}).reduce((a, b) => a + b, 0);
      toast.success(`Restauration réussie (${total} enregistrements)`);
    } catch (err) {
      toast.error(err.response ? formatApiErrorDetail(err.response?.data?.detail) : "Fichier JSON invalide");
    } finally { setBusy(""); if (fileRef.current) fileRef.current.value = ""; }
  };

  return (
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg" data-testid="backup-manager">
      <div className="p-6 border-b border-border/50">
        <p className="overline text-zinc-500">Sécurité des données</p>
        <h2 className="font-display text-2xl font-bold tracking-tight mt-1">Sauvegarde & restauration</h2>
        <p className="text-sm text-zinc-500 mt-2">
          Vos données sont sauvegardées automatiquement sur le serveur. Vous pouvez aussi télécharger une copie
          ou restaurer une sauvegarde antérieure. La restauration <strong>remplace</strong> toutes les données actuelles.
        </p>
      </div>
      <div className="p-6 flex flex-col sm:flex-row flex-wrap gap-3">
        <Button data-testid="backup-download-btn" onClick={doDownload} disabled={busy === "download"}
          className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold">
          <DownloadSimple weight="bold" size={16} className="mr-2" />
          {busy === "download" ? "Préparation…" : "Télécharger une sauvegarde"}
        </Button>
        <Button data-testid="backup-savenow-btn" onClick={doSaveNow} disabled={busy === "save"}
          variant="outline" className="rounded-full border-border/70 font-semibold">
          <FloppyDisk weight="bold" size={16} className="mr-2" />
          {busy === "save" ? "Enregistrement…" : "Sauvegarder maintenant"}
        </Button>
        <Button data-testid="backup-restore-btn" onClick={() => fileRef.current?.click()} disabled={busy === "restore"}
          variant="outline" className="rounded-full border-border/70 font-semibold">
          <UploadSimple weight="bold" size={16} className="mr-2" />
          {busy === "restore" ? "Restauration…" : "Restaurer un fichier"}
        </Button>
        <input ref={fileRef} type="file" accept="application/json,.json" onChange={onFile} className="hidden" data-testid="backup-file-input" />
      </div>
    </div>
  );
}

export default function Home() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [installations, setInstallations] = useState(null);
  const [tab, setTab] = useState("installations");
  const [code, setCode] = useState("");
  const [joinOpen, setJoinOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const canCreate = ["super_admin", "moderator", "installer"].includes(user.role);
  const isAdminView = user.role === "super_admin" || user.role === "moderator";

  const load = useCallback(async () => setInstallations(await api.listInstallations()), []);
  useEffect(() => { load(); }, [load]);

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.deleteInstallation(deleteTarget.id);
      toast.success("Installation supprimée");
      setDeleteTarget(null);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setDeleting(false);
    }
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
            <DialogContent className="bg-[#FFFFFF] border-border/70">
              <DialogHeader><DialogTitle className="font-display tracking-tight">Rejoindre une installation</DialogTitle></DialogHeader>
              <div className="py-2">
                <Label className="text-xs text-zinc-600">Code d'invitation</Label>
                <Input data-testid="join-code-input" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="EX: A1B2C3D4" className="mt-1 bg-zinc-100 border-border/70 font-mono-num tracking-widest uppercase" />
              </div>
              <DialogFooter>
                <Button data-testid="join-submit-btn" onClick={join} className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold">Rejoindre</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {canCreate && (
            <CreateInstallationDialog onCreated={(inst) => navigate(`/installations/${inst.id}`)} />
          )}
        </div>
      </div>

      {isAdminView && (
        <div className="flex gap-1 border border-border/60 bg-[#FFFFFF] rounded-full p-1 w-fit mb-6">
          {[["installations", "Installations", House], ["users", "Utilisateurs", Users],
            ...(["super_admin", "moderator"].includes(user.role) ? [["catalog", "Catalogue QR", QrCode]] : []),
            ...(user.role === "super_admin" ? [["backup", "Sauvegarde", ShieldCheck], ["tuya", "Paramètres", PlugsConnected]] : [])].map(([k, l, Icon]) => (
            <button key={k} data-testid={`admintab-${k}`} onClick={() => setTab(k)}
              className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-colors duration-200"
              style={{ background: tab === k ? "#3F3F46" : "transparent", color: tab === k ? "#FFFFFF" : "#71717A" }}>
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
            <motion.div
              key={inst.id}
              initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              className="relative"
            >
              {user.role === "super_admin" && (
                <button
                  data-testid={`delete-installation-${inst.id}`}
                  onClick={(e) => { e.stopPropagation(); setDeleteTarget(inst); }}
                  className="absolute top-3 right-3 z-10 w-8 h-8 rounded-full border border-border bg-white flex items-center justify-center text-zinc-500 hover:text-white hover:bg-offline hover:border-offline transition-colors duration-200 shadow-sm"
                  title="Supprimer l'installation"
                >
                  <Trash size={15} weight="bold" />
                </button>
              )}
              <button
                data-testid={`installation-card-${inst.id}`}
                onClick={() => navigate(`/installations/${inst.id}`)}
                className="w-full text-left border border-border/60 bg-[#FFFFFF] rounded-lg p-6 hover:border-zinc-500 transition-colors duration-200 group"
              >
                <div className="flex items-start justify-between">
                  <div className="w-11 h-11 rounded-md bg-heat/15 border border-heat/30 flex items-center justify-center">
                    <House weight="duotone" size={24} className="text-heat" />
                  </div>
                  <ArrowRight size={18} className="text-zinc-600 group-hover:text-zinc-900 transition-colors duration-200" />
                </div>
                <h3 className="font-display text-xl font-bold tracking-tight mt-4">{inst.name}</h3>
                <div className="flex flex-col gap-1 mt-3 text-xs text-zinc-500">
                  <span className="flex items-center gap-1.5"><Crown size={13} className="text-amber-400" /> {inst.owner_name || "Sans propriétaire"}</span>
                  <span className="flex items-center gap-1.5"><Wrench size={13} className="text-cool" /> {inst.installer_name || "—"}</span>
                </div>
                <span className="inline-block mt-4 text-[10px] px-2 py-0.5 rounded-full" style={{ background: inst.can_write ? "rgba(16,185,129,0.12)" : "rgba(161,161,170,0.12)", color: inst.can_write ? "#10B981" : "#71717A" }}>
                  {inst.can_write ? "Contrôle actif" : "Lecture seule"}
                </span>
              </button>
            </motion.div>
          ))}
        </div>
      )}

      {isAdminView && tab === "users" && <UsersManager />}

      {["super_admin", "moderator"].includes(user.role) && tab === "catalog" && <CatalogManager />}

      {user.role === "super_admin" && tab === "backup" && <BackupManager />}

      {user.role === "super_admin" && tab === "tuya" && <TuyaManager />}

      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent className="bg-white border-border" data-testid="delete-confirm-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display tracking-tight">Supprimer cette installation ?</AlertDialogTitle>
            <AlertDialogDescription>
              L'installation « {deleteTarget?.name} » ainsi que ses zones, appareils, plannings et invitations seront définitivement supprimés. Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="delete-cancel-btn" className="rounded-full">Annuler</AlertDialogCancel>
            <AlertDialogAction
              data-testid="delete-confirm-btn"
              onClick={(e) => { e.preventDefault(); confirmDelete(); }}
              disabled={deleting}
              className="rounded-full bg-offline text-white hover:bg-red-600"
            >
              {deleting ? "Suppression…" : "Supprimer définitivement"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  );
}
