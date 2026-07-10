import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import {
  Plus, CloudCheck, CloudSlash, ShieldCheck, CheckCircle, XCircle, CircleNotch,
  Trash, PencilSimple, LockKey, Warning, PlugsConnected,
} from "@phosphor-icons/react";
import { motion } from "framer-motion";
import api, { formatApiErrorDetail } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "./ui/alert-dialog";

const emptyForm = { name: "", region: "eu", access_id: "", access_secret: "", project_code: "" };

function isRenewDue(renewAt) {
  if (!renewAt) return false;
  return new Date(renewAt).getTime() <= Date.now();
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
}

export function TuyaManager() {
  const [projects, setProjects] = useState([]);
  const [regions, setRegions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ps, rs] = await Promise.all([api.listTuyaProjects(), api.tuyaRegions()]);
      setProjects(ps); setRegions(rs);
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEditing(null); setForm(emptyForm); setDialogOpen(true); };
  const openEdit = (p) => {
    setEditing(p);
    setForm({ name: p.name, region: p.region, access_id: "", access_secret: "", project_code: p.project_code || "" });
    setDialogOpen(true);
  };

  const save = async () => {
    if (!form.name.trim()) return toast.error("Nom du projet requis");
    if (!editing && (!form.access_id.trim() || !form.access_secret.trim()))
      return toast.error("Access ID et Access Secret requis");
    setSaving(true);
    try {
      if (editing) {
        const patch = { name: form.name, region: form.region, project_code: form.project_code };
        if (form.access_id.trim()) patch.access_id = form.access_id.trim();
        if (form.access_secret.trim()) patch.access_secret = form.access_secret.trim();
        await api.updateTuyaProject(editing.id, patch);
        toast.success("Projet mis à jour");
      } else {
        await api.createTuyaProject({ ...form, name: form.name.trim() });
        toast.success("Projet Tuya ajouté (identifiants chiffrés)");
      }
      setDialogOpen(false);
      await load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setSaving(false); }
  };

  const activate = async (p) => {
    await api.activateTuyaProject(p.id);
    toast.success(`« ${p.name} » est désormais le projet actif`);
    load();
  };

  const runTest = async (p) => {
    setTestingId(p.id);
    try {
      const res = await api.testTuyaProject(p.id);
      if (res.ok) toast.success(`Connexion réussie · ${res.device_count} appareil(s) détecté(s)`);
      else toast.error(`Échec : ${res.error}`);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setTestingId(null); load(); }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    await api.deleteTuyaProject(deleteTarget.id);
    toast("Projet supprimé");
    setDeleteTarget(null);
    load();
  };

  return (
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg" data-testid="tuya-manager">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-6 border-b border-border/50">
        <div>
          <p className="overline text-zinc-500">Connexion cloud</p>
          <h2 className="font-display text-2xl font-bold tracking-tight mt-1 flex items-center gap-2">
            <PlugsConnected weight="duotone" size={24} className="text-heat" /> Projets API
          </h2>
          <p className="text-sm text-zinc-500 mt-1 flex items-center gap-1.5">
            <LockKey size={14} className="text-online" />
            Vos identifiants sont chiffrés sur le serveur et jamais renvoyés en clair. Gardez plusieurs projets pour limiter les pertes.
          </p>
        </div>
        <Button data-testid="tuya-add-btn" onClick={openNew} className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold shrink-0">
          <Plus weight="bold" size={16} className="mr-2" /> Ajouter un projet
        </Button>
      </div>

      <div className="p-6 space-y-4">
        {loading && (
          <div className="flex items-center gap-2 text-zinc-500 py-6">
            <CircleNotch size={18} className="animate-spin text-heat" /> Chargement…
          </div>
        )}
        {!loading && projects.length === 0 && (
          <p className="text-sm text-zinc-500 py-6 text-center">Aucun projet Tuya. Ajoutez-en un pour connecter vos appareils réels.</p>
        )}
        {projects.map((p, i) => {
          const due = isRenewDue(p.renew_at);
          return (
            <motion.div
              key={p.id}
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
              data-testid={`tuya-project-${p.id}`}
              className="rounded-lg border p-4"
              style={{ borderColor: p.active ? "rgba(124,58,237,0.4)" : "#E4E4E7", background: p.active ? "rgba(124,58,237,0.04)" : "#FFFFFF" }}
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-display font-bold text-lg tracking-tight">{p.name}</h3>
                    {p.active && (
                      <span data-testid={`tuya-active-badge-${p.id}`} className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-heat/15 text-heat flex items-center gap-1">
                        <CheckCircle weight="fill" size={12} /> Actif
                      </span>
                    )}
                    {p.last_test_ok === true && <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-online/15 text-online flex items-center gap-1"><CloudCheck weight="fill" size={12} /> Connecté</span>}
                    {p.last_test_ok === false && <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-offline/15 text-offline flex items-center gap-1"><CloudSlash weight="fill" size={12} /> Échec</span>}
                    {due && <span data-testid={`tuya-renew-badge-${p.id}`} className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 flex items-center gap-1"><Warning weight="fill" size={12} /> À renouveler</span>}
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-zinc-500 font-mono-num">
                    <span>Région : {p.region_label}</span>
                    <span>ID : {p.access_id_masked}</span>
                    {p.project_code && <span>Projet : {p.project_code}</span>}
                    <span>Renouv. : {fmtDate(p.renew_at)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 flex-wrap">
                  <Button data-testid={`tuya-test-${p.id}`} onClick={() => runTest(p)} disabled={testingId === p.id}
                    variant="outline" className="rounded-full border-border/70 font-semibold h-9 text-xs">
                    {testingId === p.id ? <CircleNotch size={14} className="animate-spin mr-1.5" /> : <PlugsConnected weight="bold" size={14} className="mr-1.5" />}
                    Tester
                  </Button>
                  {!p.active && (
                    <Button data-testid={`tuya-activate-${p.id}`} onClick={() => activate(p)}
                      className="rounded-full bg-zinc-900 text-white hover:bg-zinc-800 font-semibold h-9 text-xs">
                      <ShieldCheck weight="bold" size={14} className="mr-1.5" /> Activer
                    </Button>
                  )}
                  <button data-testid={`tuya-edit-${p.id}`} onClick={() => openEdit(p)} className="w-9 h-9 rounded-full border border-border/70 flex items-center justify-center text-zinc-600 hover:text-zinc-900 transition-colors duration-200">
                    <PencilSimple size={15} />
                  </button>
                  <button data-testid={`tuya-delete-${p.id}`} onClick={() => setDeleteTarget(p)} className="w-9 h-9 rounded-full border border-border/70 flex items-center justify-center text-zinc-500 hover:text-offline transition-colors duration-200">
                    <Trash size={15} />
                  </button>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Add / Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-[#FFFFFF] border-border/70 max-w-lg" data-testid="tuya-dialog">
          <DialogHeader>
            <DialogTitle className="font-display tracking-tight text-2xl">{editing ? "Modifier le projet" : "Ajouter un projet Tuya"}</DialogTitle>
            <p className="text-sm text-zinc-500 flex items-center gap-1.5"><LockKey size={14} className="text-online" /> Les identifiants sont chiffrés sur le serveur.</p>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs text-zinc-600">Nom du projet</Label>
              <Input data-testid="tuya-form-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Ex : Projet Principal" className="mt-1 bg-zinc-100 border-border/70" />
            </div>
            <div>
              <Label className="text-xs text-zinc-600">Région / Data center</Label>
              <Select value={form.region} onValueChange={(v) => setForm({ ...form, region: v })}>
                <SelectTrigger data-testid="tuya-form-region" className="mt-1 bg-zinc-100 border-border/70 h-10"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {regions.map((r) => (<SelectItem key={r.code} value={r.code}>{r.label}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs text-zinc-600">Access ID {editing && <span className="text-zinc-400">(laisser vide pour conserver)</span>}</Label>
              <Input data-testid="tuya-form-accessid" value={form.access_id} onChange={(e) => setForm({ ...form, access_id: e.target.value })} placeholder={editing ? "••••••••" : "Votre Access ID"} className="mt-1 bg-zinc-100 border-border/70 font-mono-num" />
            </div>
            <div>
              <Label className="text-xs text-zinc-600">Access Secret {editing && <span className="text-zinc-400">(laisser vide pour conserver)</span>}</Label>
              <Input data-testid="tuya-form-secret" type="password" value={form.access_secret} onChange={(e) => setForm({ ...form, access_secret: e.target.value })} placeholder={editing ? "••••••••" : "Votre Access Secret"} className="mt-1 bg-zinc-100 border-border/70 font-mono-num" />
            </div>
            <div>
              <Label className="text-xs text-zinc-600">Code projet (optionnel)</Label>
              <Input data-testid="tuya-form-code" value={form.project_code} onChange={(e) => setForm({ ...form, project_code: e.target.value })} placeholder="Ex : p17834..." className="mt-1 bg-zinc-100 border-border/70 font-mono-num" />
            </div>
          </div>
          <DialogFooter>
            <Button data-testid="tuya-form-submit" onClick={save} disabled={saving} className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold">
              {saving ? "Enregistrement…" : editing ? "Enregistrer" : "Ajouter"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent className="bg-white border-border">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display tracking-tight">Supprimer ce projet Tuya ?</AlertDialogTitle>
            <AlertDialogDescription>« {deleteTarget?.name} » sera supprimé. Cette action est irréversible.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-full">Annuler</AlertDialogCancel>
            <AlertDialogAction data-testid="tuya-delete-confirm" onClick={(e) => { e.preventDefault(); confirmDelete(); }} className="rounded-full bg-offline text-white hover:bg-red-600">
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
