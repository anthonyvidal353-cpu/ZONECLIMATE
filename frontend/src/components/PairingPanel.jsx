import { QrCode } from "@phosphor-icons/react";
import { useState } from "react";
import { QrAssociateDialog } from "./QrAssociateDialog";
import { Button } from "./ui/button";

// Côté client / installateur : association UNIQUEMENT par scan de QR code.
// Aucune liste d'appareils n'est exposée (évite de sélectionner par erreur un
// appareil ne leur appartenant pas). La découverte + génération de QR se fait
// côté super admin / modérateur (onglet « Catalogue QR »).
export const PairingPanel = ({ iid, zones, onAssociated }) => {
  const [qrOpen, setQrOpen] = useState(false);

  return (
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg" data-testid="pairing-panel">
      <QrAssociateDialog open={qrOpen} onOpenChange={setQrOpen} iid={iid} zones={zones} onAssociated={onAssociated} />

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-6 bg-heat/5 rounded-lg">
        <div className="flex items-start gap-3">
          <div className="w-11 h-11 rounded-full bg-heat/15 flex items-center justify-center shrink-0">
            <QrCode weight="duotone" size={22} className="text-heat" />
          </div>
          <div>
            <h2 className="font-display text-xl font-bold tracking-tight">Ajouter un appareil</h2>
            <p className="text-xs text-zinc-500 mt-0.5 max-w-md">
              Scannez le <strong>QR code</strong> collé sur l'appareil pour l'associer à une zone.
              L'association est <strong>garantie sans erreur</strong> — seul l'appareil scanné est ajouté.
            </p>
          </div>
        </div>
        <Button data-testid="open-qr-scan-btn" onClick={() => setQrOpen(true)}
          className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold shrink-0 h-11">
          <QrCode weight="bold" size={18} className="mr-2" /> Scanner un QR code
        </Button>
      </div>
    </div>
  );
};
