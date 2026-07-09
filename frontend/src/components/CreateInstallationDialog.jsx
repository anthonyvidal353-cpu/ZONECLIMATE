import { useState } from "react";
import { Plus, Trash, Wind, Thermometer, Crown, WifiHigh, Cube } from "@phosphor-icons/react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "../lib/api";
import { zoneIcons } from "../lib/icons";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "./ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

const ICON_OPTIONS = Object.keys(zoneIcons);
const rand = () => Math.floor(1000 + Math.random() * 9000);
const newThermoId = () => `SL-THERMO-${rand()}`;
const newDuctId = () => `SL-DUCT-${rand()}`;
const uid = () => Math.random().toString(36).slice(2, 9);

function emptyZone(master = false, icon = "house", name = "") {
  return { key: uid(), name, icon, master, product_id: "" };
}

export const CreateInstallationDialog = ({ onCreated }) => {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [gainableName, setGainableName] = useState("Gainable Principal");
  const [gainableId, setGainableId] = useState("");
  const [zones, setZones] = useState([
    emptyZone(true, "couch", "Salon"),
    emptyZone(false, "bed", "Chambre"),
  ]);

  const reset = () => {
    setName(""); setGainableName("Gainable Principal"); setGainableId("");
    setZones([emptyZone(true, "couch", "Salon"), emptyZone(false, "bed", "Chambre")]);
  };

  const setZone = (key, patch) => setZones((zs) => zs.map((z) => (z.key === key ? { ...z, ...patch } : z)));
  const addZone = () => setZones((zs) => [...zs, emptyZone(false, "house", "")]);
  const removeZone = (key) => setZones((zs) => (zs.length > 1 ? zs.filter((z) => z.key !== key) : zs));
  const setMaster = (key) => setZones((zs) => zs.map((z) => ({ ...z, master: z.key === key })));

  const autoAssociate = () => {
    setGainableId(newDuctId());
    setZones((zs) => zs.map((z) => ({ ...z, product_id: newThermoId() })));
    toast.success("Appareils SmartLife associés (simulé)");
  };

  const submit = async () => {
    if (!name.trim()) return toast.error("Nom de l'installation requis");
    const cleanZones = zones.filter((z) => z.name.trim());
    if (cleanZones.length === 0) return toast.error("Ajoutez au moins une zone");
    if (!cleanZones.some((z) => z.master)) cleanZones[0].master = true;

    const payload = {
      name: name.trim(),
      gainable: { name: gainableName.trim() || "Gainable Principal", product_id: gainableId.trim() || newDuctId() },
      zones: cleanZones.map((z) => ({
        name: z.name.trim(),
        icon: z.icon,
        master: z.master,
        thermostat: { name: `Thermostat ${z.name.trim()}`, product_id: z.product_id.trim() || newThermoId() },
      })),
    };
    setBusy(true);
    try {
      const inst = await api.createInstallation(payload);
      toast.success("Installation créée avec l'association SmartLife");
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
        <Button data-testid="create-installation-btn" className="rounded-full bg-heat text-black hover:bg-heat-soft font-semibold">
          <Plus weight="bold" size={16} className="mr-2" /> Nouvelle installation
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-[#121212] border-border/70 max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display tracking-tight text-2xl">Créer une installation</DialogTitle>
          <p className="text-sm text-zinc-500">Associez le gainable et les thermostats SmartLife, zone par zone.</p>
        </DialogHeader>

        <div className="space-y-5 py-2">
          <div>
            <Label className="text-xs text-zinc-400">Nom de l'installation</Label>
            <Input data-testid="installation-name-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex : Maison Dupont" className="mt-1 bg-black/40 border-border/70" />
          </div>

          <div className="flex justify-end">
            <button data-testid="auto-associate-btn" onClick={autoAssociate} className="inline-flex items-center gap-1.5 text-xs font-semibold text-heat hover:underline">
              <WifiHigh weight="bold" size={14} /> Associer les appareils SmartLife (simulé)
            </button>
          </div>

          {/* Gainable */}
          <div className="rounded-md border border-border/60 bg-black/30 p-4">
            <div className="flex items-center gap-2 mb-3">
              <Wind weight="duotone" size={18} className="text-heat" />
              <span className="overline text-zinc-400">Gainable (unité principale)</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs text-zinc-500">Nom</Label>
                <Input data-testid="gainable-name-input" value={gainableName} onChange={(e) => setGainableName(e.target.value)} className="mt-1 bg-black/40 border-border/70" />
              </div>
              <div>
                <Label className="text-xs text-zinc-500">ID produit SmartLife</Label>
                <Input data-testid="gainable-id-input" value={gainableId} onChange={(e) => setGainableId(e.target.value)} placeholder="SL-DUCT-XXXX" className="mt-1 bg-black/40 border-border/70 font-mono-num" />
              </div>
            </div>
          </div>

          {/* Zones */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Thermometer weight="duotone" size={18} className="text-cool" />
                <span className="overline text-zinc-400">Zones & thermostats</span>
              </div>
              <button data-testid="add-zone-btn" onClick={addZone} className="inline-flex items-center gap-1 text-xs font-semibold text-zinc-300 hover:text-white transition-colors duration-200">
                <Plus weight="bold" size={14} /> Ajouter une zone
              </button>
            </div>

            <div className="space-y-3">
              {zones.map((z, i) => (
                <div key={z.key} data-testid={`zone-row-${i}`} className="rounded-md border border-border/60 bg-black/30 p-3">
                  <div className="grid grid-cols-1 sm:grid-cols-[1fr_120px] gap-3">
                    <div>
                      <Label className="text-xs text-zinc-500">Nom de la zone</Label>
                      <Input data-testid={`zone-name-${i}`} value={z.name} onChange={(e) => setZone(z.key, { name: e.target.value })} placeholder="Ex : Salon" className="mt-1 bg-black/40 border-border/70" />
                    </div>
                    <div>
                      <Label className="text-xs text-zinc-500">Pièce</Label>
                      <Select value={z.icon} onValueChange={(v) => setZone(z.key, { icon: v })}>
                        <SelectTrigger data-testid={`zone-icon-${i}`} className="mt-1 bg-black/40 border-border/70 h-10 capitalize">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ICON_OPTIONS.map((ic) => (<SelectItem key={ic} value={ic} className="capitalize">{ic}</SelectItem>))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_auto] gap-3 items-end mt-3">
                    <div>
                      <Label className="text-xs text-zinc-500">ID thermostat SmartLife</Label>
                      <Input data-testid={`zone-thermo-${i}`} value={z.product_id} onChange={(e) => setZone(z.key, { product_id: e.target.value })} placeholder="SL-THERMO-XXXX" className="mt-1 bg-black/40 border-border/70 font-mono-num" />
                    </div>
                    <button
                      data-testid={`zone-master-${i}`}
                      onClick={() => setMaster(z.key)}
                      className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-xs font-semibold border transition-colors duration-200"
                      style={{ borderColor: z.master ? "#F59E0B" : "#27272A", background: z.master ? "rgba(245,158,11,0.12)" : "transparent", color: z.master ? "#F59E0B" : "#A1A1AA" }}
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
          <Button data-testid="create-submit-btn" onClick={submit} disabled={busy} className="rounded-full bg-heat text-black hover:bg-heat-soft font-semibold">
            {busy ? "Création…" : "Créer l'installation"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
