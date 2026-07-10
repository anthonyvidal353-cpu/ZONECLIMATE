import { useState } from "react";
import { Plus, Trash, Thermometer, Crown, HouseLine, Info } from "@phosphor-icons/react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "../lib/api";
import { zoneIcons, PIECE_LABELS } from "../lib/icons";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger, DialogDescription } from "./ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

const ICON_OPTIONS = Object.keys(zoneIcons);
const uid = () => Math.random().toString(36).slice(2, 9);

function emptyZone(master = false, icon = "house", name = "") {
  return { key: uid(), name, icon, master };
}

// Modèles de logement : pré-remplissage rapide des zones
const HOUSING_TEMPLATES = {
  studio: { label: "Studio", zones: [["Salon", "couch", true]] },
  t2: { label: "T2", zones: [["Salon", "couch", true], ["Chambre", "bed", false]] },
  t3: { label: "T3", zones: [["Salon", "couch", true], ["Chambre 1", "bed", false], ["Chambre 2", "bed", false]] },
  maison: {
    label: "Maison",
    zones: [
      ["Salon", "couch", true], ["Cuisine", "fork", false], ["Chambre parentale", "bed", false],
      ["Chambre enfant", "baby", false], ["Bureau", "desktop", false], ["Salle de bain", "shower", false],
    ],
  },
};

export const CreateInstallationDialog = ({ onCreated }) => {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [zones, setZones] = useState([
    emptyZone(true, "couch", "Salon"),
    emptyZone(false, "bed", "Chambre"),
  ]);

  const reset = () => {
    setName("");
    setZones([emptyZone(true, "couch", "Salon"), emptyZone(false, "bed", "Chambre")]);
  };

  const setZone = (key, patch) => setZones((zs) => zs.map((z) => (z.key === key ? { ...z, ...patch } : z)));
  const addZone = () => setZones((zs) => [...zs, emptyZone(false, "house", "")]);
  const removeZone = (key) => setZones((zs) => (zs.length > 1 ? zs.filter((z) => z.key !== key) : zs));
  const setMaster = (key) => setZones((zs) => zs.map((z) => ({ ...z, master: z.key === key })));

  const applyTemplate = (key) => {
    const tpl = HOUSING_TEMPLATES[key];
    if (!tpl) return;
    setZones(tpl.zones.map(([nm, ic, master]) => emptyZone(master, ic, nm)));
    toast.success(`Modèle « ${tpl.label} » appliqué`);
  };

  const submit = async () => {
    if (!name.trim()) return toast.error("Nom de l'installation requis");
    // Nomme automatiquement les zones sans nom (« Zone 1 », « Zone 2 »…).
    const used = new Set(zones.map((z) => z.name.trim()).filter(Boolean));
    let counter = 0;
    const nextAutoName = () => {
      let candidate;
      do { counter += 1; candidate = `Zone ${counter}`; } while (used.has(candidate));
      used.add(candidate);
      return candidate;
    };
    const cleanZones = zones.map((z) => ({ ...z, name: z.name.trim() || nextAutoName() }));
    if (cleanZones.length === 0) return toast.error("Ajoutez au moins une zone");
    if (!cleanZones.some((z) => z.master)) cleanZones[0].master = true;

    const payload = {
      name: name.trim(),
      zones: cleanZones.map((z) => ({ name: z.name.trim(), icon: z.icon, master: z.master })),
    };
    setBusy(true);
    try {
      const inst = await api.createInstallation(payload);
      toast.success("Installation créée — associez vos appareils dans l'onglet Appareils");
      setOpen(false); reset();
      onCreated?.(inst);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) reset(); }}>
      <DialogTrigger asChild>
        <Button data-testid="create-installation-btn" className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold">
          <Plus weight="bold" size={16} className="mr-2" /> Nouvelle installation
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-[#FFFFFF] border-border/70 max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display tracking-tight text-2xl">Créer une installation</DialogTitle>
          <DialogDescription className="text-sm text-zinc-500">
            Définissez les zones (pièces) de votre logement. Vous associerez ensuite vos appareils réels à chaque zone.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          <div>
            <Label className="text-xs text-zinc-600">Nom de l'installation</Label>
            <Input data-testid="installation-name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex : Maison Dupont" className="mt-1 bg-zinc-100 border-border/70" />
          </div>

          <div>
            <Label className="text-xs text-zinc-600">Modèle de logement (optionnel)</Label>
            <div className="flex flex-wrap gap-2 mt-1.5">
              {Object.entries(HOUSING_TEMPLATES).map(([key, tpl]) => (
                <button
                  key={key}
                  type="button"
                  data-testid={`template-${key}`}
                  onClick={() => applyTemplate(key)}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-white px-3.5 py-1.5 text-xs font-semibold text-zinc-700 hover:border-heat hover:text-heat transition-colors duration-200"
                >
                  <HouseLine weight="duotone" size={14} /> {tpl.label}
                </button>
              ))}
            </div>
          </div>

          {/* Zones */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Thermometer weight="duotone" size={18} className="text-cool" />
                <span className="overline text-zinc-600">Zones (pièces)</span>
              </div>
              <button data-testid="add-zone-btn" onClick={addZone} className="inline-flex items-center gap-1 text-xs font-semibold text-zinc-700 hover:text-zinc-900 transition-colors duration-200">
                <Plus weight="bold" size={14} /> Ajouter une zone
              </button>
            </div>

            <div className="space-y-3">
              {zones.map((z, i) => (
                <div key={z.key} data-testid={`zone-row-${i}`} className="rounded-md border border-border/60 bg-zinc-50 p-3">
                  <div className="grid grid-cols-1 sm:grid-cols-[1fr_150px_auto_auto] gap-3 items-end">
                    <div>
                      <Label className="text-xs text-zinc-500">Nom de la zone</Label>
                      <Input data-testid={`zone-name-${i}`} value={z.name} onChange={(e) => setZone(z.key, { name: e.target.value })} placeholder="Ex : Salon" className="mt-1 bg-zinc-100 border-border/70" />
                    </div>
                    <div>
                      <Label className="text-xs text-zinc-500">Pièce</Label>
                      <Select value={z.icon} onValueChange={(v) => setZone(z.key, { icon: v })}>
                        <SelectTrigger data-testid={`zone-icon-${i}`} className="mt-1 bg-zinc-100 border-border/70 h-10">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ICON_OPTIONS.map((ic) => (<SelectItem key={ic} value={ic}>{PIECE_LABELS[ic] || ic}</SelectItem>))}
                        </SelectContent>
                      </Select>
                    </div>
                    <button
                      data-testid={`zone-master-${i}`}
                      onClick={() => setMaster(z.key)}
                      className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-xs font-semibold border transition-colors duration-200 h-10"
                      style={{ borderColor: z.master ? "#F59E0B" : "#E4E4E7", background: z.master ? "rgba(245,158,11,0.12)" : "transparent", color: z.master ? "#F59E0B" : "#71717A" }}
                    >
                      <Crown weight={z.master ? "fill" : "regular"} size={14} /> Maître
                    </button>
                    <button data-testid={`zone-remove-${i}`} onClick={() => removeZone(z.key)} className="w-10 h-10 rounded-full border border-border/70 flex items-center justify-center text-zinc-500 hover:text-offline transition-colors duration-200">
                      <Trash size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Note appairage réel */}
          <div className="flex items-start gap-2 rounded-md border border-cool/30 bg-cool/5 p-3">
            <Info weight="fill" size={18} className="text-cool shrink-0 mt-0.5" />
            <p className="text-xs text-zinc-600 leading-relaxed">
              Après la création, ouvrez l'onglet <strong>Appareils</strong> puis <strong>« Rechercher des appareils »</strong> (mode Réel)
              pour retrouver votre gainable et vos thermostats déjà présents dans votre compte, et les associer à ces zones.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button data-testid="create-submit-btn" onClick={submit} disabled={busy} className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold">
            {busy ? "Création…" : "Créer l'installation"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
