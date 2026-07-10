import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Html5Qrcode } from "html5-qrcode";
import { QrCode, Camera, CircleNotch, Keyboard } from "@phosphor-icons/react";
import api, { formatApiErrorDetail } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

const READER_ID = "qr-reader-region";

export const QrAssociateDialog = ({ open, onOpenChange, iid, zones = [], onAssociated }) => {
  const [step, setStep] = useState("scan"); // scan | zone
  const [code, setCode] = useState("");
  const [manual, setManual] = useState(false);
  const [manualCode, setManualCode] = useState("");
  const [zoneChoice, setZoneChoice] = useState("");
  const [newZoneName, setNewZoneName] = useState("");
  const [busy, setBusy] = useState(false);
  const scannerRef = useRef(null);

  const stopScanner = async () => {
    const s = scannerRef.current;
    scannerRef.current = null;
    if (s) {
      try { await s.stop(); } catch (_) { /* ignore */ }
      try { await s.clear(); } catch (_) { /* ignore */ }
    }
  };

  const startScanner = async () => {
    try {
      const qr = new Html5Qrcode(READER_ID);
      scannerRef.current = qr;
      await qr.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 220, height: 220 } },
        async (decoded) => {
          await stopScanner();
          const c = decoded.trim().toUpperCase().replace("ZONECLIMATE:", "");
          setCode(c);
          setZoneChoice(zones[0]?.id || "__new__");
          setStep("zone");
        },
        () => { /* frame sans QR : ignorer */ },
      );
    } catch (e) {
      setManual(true);
      toast.error("Caméra indisponible. Saisissez le code manuellement.");
    }
  };

  useEffect(() => {
    if (open && step === "scan" && !manual) {
      const t = setTimeout(startScanner, 300);
      return () => { clearTimeout(t); stopScanner(); };
    }
    return () => {};
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, step, manual]);

  useEffect(() => {
    if (!open) {
      stopScanner();
      setStep("scan"); setCode(""); setManual(false); setManualCode("");
      setZoneChoice(""); setNewZoneName("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const useManual = () => {
    const c = manualCode.trim().toUpperCase().replace("ZONECLIMATE:", "");
    if (!c) return toast.error("Saisissez un code");
    setCode(c);
    setZoneChoice(zones[0]?.id || "__new__");
    setStep("zone");
  };

  const associate = async () => {
    const body = { code };
    if (zoneChoice === "__new__") {
      if (!newZoneName.trim()) return toast.error("Nom de la nouvelle zone requis");
      body.new_zone_name = newZoneName.trim();
    } else {
      body.zone_id = zoneChoice;
    }
    setBusy(true);
    try {
      const res = await api.associateQR(iid, body);
      toast.success(`« ${res.device.name} » associé avec succès`);
      onAssociated?.(res);
      onOpenChange(false);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#FFFFFF] border-border/70 max-w-md" data-testid="qr-associate-dialog">
        <DialogHeader>
          <DialogTitle className="font-display tracking-tight text-2xl flex items-center gap-2">
            <QrCode weight="duotone" size={24} className="text-heat" /> Associer par QR code
          </DialogTitle>
          <DialogDescription className="text-sm text-zinc-500">
            {step === "scan" ? "Scannez l'étiquette QR collée sur l'appareil." : "Choisissez la pièce à laquelle rattacher cet appareil."}
          </DialogDescription>
        </DialogHeader>

        {step === "scan" && (
          <div className="space-y-3">
            {!manual ? (
              <>
                <div id={READER_ID} data-testid="qr-reader" className="rounded-lg overflow-hidden border border-border/60 bg-black/5 min-h-[240px] flex items-center justify-center">
                  <span className="text-xs text-zinc-400 flex items-center gap-2"><Camera size={16} /> Activation de la caméra…</span>
                </div>
                <button data-testid="qr-manual-toggle" onClick={() => { stopScanner(); setManual(true); }} className="text-xs text-zinc-500 hover:text-zinc-800 flex items-center gap-1.5 mx-auto transition-colors duration-200">
                  <Keyboard size={14} /> Saisir le code manuellement
                </button>
              </>
            ) : (
              <div className="space-y-2">
                <Label className="text-xs text-zinc-600">Code de l'appareil (sous le QR)</Label>
                <Input data-testid="qr-manual-input" value={manualCode} onChange={(e) => setManualCode(e.target.value)} placeholder="Ex : CZ-AB12CD34" className="bg-zinc-100 border-border/70 font-mono-num" />
                <Button data-testid="qr-manual-submit" onClick={useManual} className="w-full rounded-full bg-heat text-white hover:bg-heat-soft font-semibold">Valider le code</Button>
              </div>
            )}
          </div>
        )}

        {step === "zone" && (
          <div className="space-y-4">
            <div className="rounded-md bg-heat/5 border border-heat/20 p-3 text-sm">
              <span className="text-zinc-500">Appareil détecté : </span>
              <span className="font-mono-num font-semibold text-heat">{code}</span>
            </div>
            <div>
              <Label className="text-xs text-zinc-600">Pièce / zone</Label>
              <Select value={zoneChoice} onValueChange={setZoneChoice}>
                <SelectTrigger data-testid="qr-zone-select" className="mt-1 bg-zinc-100 border-border/70 h-10"><SelectValue placeholder="Choisir une zone" /></SelectTrigger>
                <SelectContent>
                  {zones.map((z) => (<SelectItem key={z.id} value={z.id}>{z.name}</SelectItem>))}
                  <SelectItem value="__new__">➕ Nouvelle zone…</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {zoneChoice === "__new__" && (
              <div>
                <Label className="text-xs text-zinc-600">Nom de la nouvelle zone</Label>
                <Input data-testid="qr-newzone-input" value={newZoneName} onChange={(e) => setNewZoneName(e.target.value)} placeholder="Ex : Bureau" className="mt-1 bg-zinc-100 border-border/70" />
              </div>
            )}
            <Button data-testid="qr-associate-submit" onClick={associate} disabled={busy} className="w-full rounded-full bg-heat text-white hover:bg-heat-soft font-semibold">
              {busy ? <CircleNotch size={16} className="animate-spin mr-2" /> : null}
              {busy ? "Association…" : "Associer l'appareil"}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
