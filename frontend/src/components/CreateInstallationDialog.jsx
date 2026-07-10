import { useState } from "react";
import { Plus, Trash, Wind, Thermometer, Crown, WifiHigh, CheckCircle, CircleNotch, HouseLine } from "@phosphor-icons/react";
import { QRCodeSVG } from "qrcode.react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "../lib/api";
import { zoneIcons, PIECE_LABELS } from "../lib/icons";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "./ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

const ICON_OPTIONS = Object.keys(zoneIcons);
const newRef = () => "CZ-" + Math.random().toString(16).slice(2, 10).toUpperCase();
const uid = () => Math.random().toString(36).slice(2, 9);

function emptyZone(master = false, icon = "house", name = "") {
  return { key: uid(), name, icon, master, ref_code: "" };
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
  const [gainableName, setGainableName] = useState("Gainable Principal");
  const [gainableRef, setGainableRef] = useState("");
  const [zones, setZones] = useState([
    emptyZone(true, "couch", "Salon"),
    emptyZone(false, "bed", "Chambre"),
  ]);
  const [pairingKey, setPairingKey] = useState(null); // "gainable" | zone.key en cours d'appairage

  const reset = () => {
    setName(""); setGainableName("Gainable Principal"); setGainableRef("");
    setPairingKey(null);
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

  const autoAssociate = () => {
    setGainableRef(newRef());
    setZones((zs) => zs.map((z) => ({ ...z, ref_code: newRef() })));
    toast.success("Références (QR) générées");
  };

  const pairGainable = () => {
    setPairingKey("gainable");
    toast.message("ZoneClimate interroge le cloud…");
    setTimeout(() => {
      setGainableRef(newRef());
      setPairingKey(null);
      toast.success("Gainable appairé");
    }, 700);
  };

  const pairZone = (zoneKey) => {
    setPairingKey(zoneKey);
    toast.message("ZoneClimate interroge le cloud…");
    setTimeout(() => {
      setZones((zs) => zs.map((z) => (z.key === zoneKey ? { ...z, ref_code: newRef() } : z)));
      setPairingKey(null);
      toast.success("Thermostat appairé");
    }, 700);
  };

  const submit = async () => {
    if (!name.trim()) return toast.error("Nom de l'installation requis");
    // Nomme automatiquement les zones sans nom (« Zone 1 », « Zone 2 »…),
    // en évitant toute collision avec les noms déjà saisis.
    const used = new Set(zones.map((z) => z.name.trim()).filter(Boolean));
    let counter = 0;
    const nextAutoName = () => {
      let candidate;
      do { counter += 1; candidate = `Zone ${counter}`; } while (used.has(candidate));
      used.add(candidate);
      return candidate;
    };
    const cleanZones = zones.map((z) => {
      const nm = z.name.trim();
      return { ...z, name: nm || nextAutoName() };
    });
    if (cleanZones.length === 0) return toast.error("Ajoutez au moins une zone");
    if (!cleanZones.some((z) => z.master)) cleanZones[0].master = true;

    const payload = {
      name: name.trim(),
      gainable: { name: gainableName.trim() || "Gainable Principal", ref_code: gainableRef.trim() || newRef() },
      zones: cleanZones.map((z) => ({
        name: z.name.trim(),
        icon: z.icon,
        master: z.master,
        thermostat: { name: `Thermostat ${z.name.trim()}`, ref_code: z.ref_code.trim() || newRef() },
      })),
    };
    setBusy(true);
    try {
      const inst = await api.createInstallation(payload);
      toast.success("Installation créée");
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
          <p className="text-sm text-zinc-500">Définissez les zones. Chaque appareil sera appairé et un QR code (référence) lui sera associé.</p>
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
            <p className="text-[11px] text-zinc-400 mt-1">Pré-remplit les zones ; vous pouvez ensuite les ajuster.</p>
          </div>

          <div className="flex justify-end">
            <button data-testid="auto-associate-btn" onClick={autoAssociate} className="inline-flex items-center gap-1.5 text-xs font-semibold text-heat hover:underline">
              <WifiHigh weight="bold" size={14} /> Tout appairer automatiquement
            </button>
          </div>

          {/* Gainable */}
          <div className="rounded-md border border-border/60 bg-zinc-50 p-4">
            <div className="flex items-center gap-2 mb-3">
              <Wind weight="duotone" size={18} className="text-heat" />
              <span className="overline text-zinc-600">Gainable (unité principale)</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs text-zinc-500">Nom</Label>
                <Input data-testid="gainable-name-input" value={gainableName} onChange={(e) => setGainableName(e.target.value)} className="mt-1 bg-zinc-100 border-border/70" />
              </div>
              <div>
                <Label className="text-xs text-zinc-500">Appareil (appairage)</Label>
                <div className="flex items-center gap-2 mt-1">
                  {gainableRef ? (
                    <div className="flex items-center gap-2 flex-1 rounded-md border border-online/40 bg-online/10 px-3 h-10">
                      <div className="bg-white p-0.5 rounded"><QRCodeSVG value={`ZONECLIMATE:${gainableRef}`} size={22} /></div>
                      <span className="font-mono-num text-sm text-online">{gainableRef}</span>
                      <CheckCircle weight="fill" size={16} className="text-online ml-auto" />
                    </div>
                  ) : (
                    <span className="flex-1 text-sm text-zinc-500 h-10 flex items-center px-1">Non appairé</span>
                  )}
                  <Button
                    type="button"
                    data-testid="gainable-pair-btn"
                    onClick={pairGainable}
                    disabled={pairingKey === "gainable"}
                    className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold h-10 shrink-0"
                  >
                    {pairingKey === "gainable"
                      ? <CircleNotch size={15} className="animate-spin mr-1.5" />
                      : <WifiHigh weight="bold" size={15} className="mr-1.5" />}
                    {gainableRef ? "Ré-appairer" : "Appairer"}
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Zones */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Thermometer weight="duotone" size={18} className="text-cool" />
                <span className="overline text-zinc-600">Zones & thermostats</span>
              </div>
              <button data-testid="add-zone-btn" onClick={addZone} className="inline-flex items-center gap-1 text-xs font-semibold text-zinc-700 hover:text-zinc-900 transition-colors duration-200">
                <Plus weight="bold" size={14} /> Ajouter une zone
              </button>
            </div>

            <div className="space-y-3">
              {zones.map((z, i) => (
                <div key={z.key} data-testid={`zone-row-${i}`} className="rounded-md border border-border/60 bg-zinc-50 p-3">
                  <div className="grid grid-cols-1 sm:grid-cols-[1fr_120px] gap-3">
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
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_auto] gap-3 items-end mt-3">
                    <div className="sm:col-span-1">
                      <Label className="text-xs text-zinc-500">Thermostat (appairage)</Label>
                      <div className="flex items-center gap-2 mt-1">
                        {z.ref_code ? (
                          <div className="flex items-center gap-2 flex-1 rounded-md border border-online/40 bg-online/10 px-2 h-9 min-w-0">
                            <div className="bg-white p-0.5 rounded shrink-0"><QRCodeSVG value={`ZONECLIMATE:${z.ref_code}`} size={18} /></div>
                            <span className="font-mono-num text-xs text-online truncate">{z.ref_code}</span>
                          </div>
                        ) : (
                          <span className="flex-1 text-xs text-zinc-500 h-9 flex items-center">Non appairé</span>
                        )}
                        <Button
                          type="button"
                          data-testid={`zone-pair-${i}`}
                          onClick={() => pairZone(z.key)}
                          disabled={pairingKey === z.key}
                          className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold h-9 text-xs shrink-0"
                        >
                          {pairingKey === z.key
                            ? <CircleNotch size={13} className="animate-spin mr-1" />
                            : <WifiHigh weight="bold" size={13} className="mr-1" />}
                          {z.ref_code ? "Ré-appairer" : "Appairer"}
                        </Button>
                      </div>
                    </div>
                    <button
                      data-testid={`zone-master-${i}`}
                      onClick={() => setMaster(z.key)}
                      className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-xs font-semibold border transition-colors duration-200"
                      style={{ borderColor: z.master ? "#F59E0B" : "#E4E4E7", background: z.master ? "rgba(245,158,11,0.12)" : "transparent", color: z.master ? "#F59E0B" : "#71717A" }}
                    >
                      <Crown weight={z.master ? "fill" : "regular"} size={14} /> Maître
                    </button>
                    <button data-testid={`zone-remove-${i}`} onClick={() => removeZone(z.key)} className="w-9 h-9 rounded-full border border-border/70 flex items-center justify-center text-zinc-500 hover:text-offline transition-colors duration-200">
                      <Trash size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button data-testid="create-submit-btn" onClick={submit} disabled={busy || pairingKey !== null} className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold">
            {busy ? "Création…" : "Créer l'installation"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
