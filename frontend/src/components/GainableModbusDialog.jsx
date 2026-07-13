import { useState } from "react";
import { toast } from "sonner";
import { Cpu, CircleNotch, PlugsConnected, FloppyDisk } from "@phosphor-icons/react";
import api, { formatApiErrorDetail } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Switch } from "./ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "./ui/dialog";

export const GainableModbusDialog = ({ open, onOpenChange, iid, system, onSaved }) => {
  const [enabled, setEnabled] = useState(!!system?.modbus_enabled);
  const [port, setPort] = useState(system?.modbus_port || "/dev/ttyUSB0");
  const [slave, setSlave] = useState(String(system?.modbus_slave || 1));
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState(null);

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api.updateSystem(iid, {
        modbus_enabled: enabled, modbus_port: port.trim(), modbus_slave: Number(slave) || 1,
      });
      onSaved?.(updated);
      toast.success("Configuration Modbus enregistrée");
      onOpenChange(false);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setSaving(false); }
  };

  const test = async () => {
    setTesting(true); setResult(null);
    try {
      // On sauvegarde d'abord le port/adresse pour tester la bonne cible
      await api.updateSystem(iid, { modbus_port: port.trim(), modbus_slave: Number(slave) || 1 });
      const res = await api.testGainableModbus(iid);
      setResult(res);
      if (res.ok) {
        toast.success(`Gainable détecté · ambiance ${res.room_temp} °C`);
        try { onSaved?.(await api.getSystem(iid)); } catch { /* ignore */ }
      } else {
        toast.error("Pas de réponse du gainable");
      }
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setTesting(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#FFFFFF] border-border/70 max-w-lg" data-testid="modbus-dialog">
        <DialogHeader>
          <DialogTitle className="font-display tracking-tight flex items-center gap-2">
            <Cpu weight="duotone" size={20} className="text-heat" /> Gainable — Pilotage Modbus (RS485)
          </DialogTitle>
          <DialogDescription className="text-sm text-zinc-500">
            Le gainable est piloté en Modbus RTU via l'automate (dongle USB-RS485). 9600 bps, sans parité, 8N1.
            Ne fonctionne que sur l'automate raccordé au bus.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="flex items-center justify-between rounded-lg border border-border/60 px-4 py-3">
            <div>
              <p className="font-semibold text-sm">Activer le pilotage Modbus du gainable</p>
              <p className="text-xs text-zinc-500">Si désactivé, le gainable n'est pas commandé par l'automate.</p>
            </div>
            <Switch data-testid="modbus-enabled-switch" checked={enabled} onCheckedChange={setEnabled} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label className="text-xs text-zinc-600">Port série</Label>
              <Input data-testid="modbus-port-input" value={port} onChange={(e) => setPort(e.target.value)}
                placeholder="/dev/ttyUSB0" className="mt-1 bg-zinc-100 border-border/70 h-10 font-mono-num" />
            </div>
            <div>
              <Label className="text-xs text-zinc-600">Adresse esclave (Slave ID)</Label>
              <Input data-testid="modbus-slave-input" type="number" min="1" max="247" value={slave}
                onChange={(e) => setSlave(e.target.value)} className="mt-1 bg-zinc-100 border-border/70 h-10 font-mono-num" />
            </div>
          </div>

          <Button data-testid="modbus-test-btn" onClick={test} disabled={testing}
            variant="outline" className="rounded-full border-border/70 font-semibold w-full">
            {testing ? <CircleNotch size={16} className="animate-spin mr-2" /> : <PlugsConnected weight="bold" size={16} className="mr-2" />}
            Tester la connexion (lire la température)
          </Button>

          {result && (
            <div data-testid="modbus-test-result" className={`rounded-md text-xs px-3 py-2 ${result.ok ? "bg-online/10 text-online" : "bg-offline/10 text-offline"}`}>
              {result.ok
                ? `✓ Gainable détecté sur ${result.port} (esclave ${result.slave}) — ambiance ${result.room_temp} °C · reprise d'air ${result.return_temp ?? "—"} °C · extérieur ${result.outdoor_temp ?? "—"} °C`
                : `✗ ${result.error}`}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} className="rounded-full border-border/70">Fermer</Button>
          <Button data-testid="modbus-save-btn" onClick={save} disabled={saving}
            className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold">
            {saving ? <CircleNotch size={16} className="animate-spin mr-2" /> : <FloppyDisk weight="bold" size={16} className="mr-2" />}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
