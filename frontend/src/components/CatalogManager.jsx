import { useEffect, useState, useCallback, useRef } from "react";
import { toast } from "sonner";
import { QRCodeCanvas } from "qrcode.react";
import { MagnifyingGlass, CircleNotch, Printer, Wind, Thermometer, CheckCircle, QrCode } from "@phosphor-icons/react";
import api, { formatApiErrorDetail } from "../lib/api";
import { Button } from "./ui/button";

export function CatalogManager() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const gridRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setItems(await api.listCatalog()); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const discover = async () => {
    setScanning(true);
    try {
      const res = await api.catalogDiscover();
      const list = res.items || res;
      setItems(list);
      (res.errors || []).forEach((e) => toast.error(`Projet « ${e.project} » : ${e.error}`));
      toast.success(`${list.length} appareil(s) au catalogue (tous projets)`);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setScanning(false); }
  };

  const LABEL_STYLE = `
      body{font-family:system-ui,Arial,sans-serif;margin:16px}
      .grid{display:flex;flex-wrap:wrap;gap:16px}
      .label{border:1px solid #ccc;border-radius:8px;padding:12px;width:190px;text-align:center;page-break-inside:avoid}
      .label img{width:150px;height:150px}
      .nm{font-weight:700;margin-top:6px;font-size:13px}
      .cd{font-family:monospace;font-size:12px;color:#555}
      .cat{font-size:11px;color:#7C3AED;margin-top:2px}`;

  const labelHtml = (it, url) =>
    `<div class="label"><img src="${url}"/><div class="nm">${it.name || ""}</div><div class="cd">${it.code}</div><div class="cat">${it.category === "gainable" ? "Gainable" : "Thermostat"}</div></div>`;

  const openPrint = (cardsHtml, title) => {
    const w = window.open("", "_blank", "width=800,height=900");
    w.document.write(`<html><head><title>${title}</title><style>${LABEL_STYLE}</style></head><body><div class="grid">${cardsHtml}</div><script>window.onload=function(){window.print();}<\/script></body></html>`);
    w.document.close();
  };

  const printLabels = () => {
    if (!gridRef.current || items.length === 0) return;
    const canvases = gridRef.current.querySelectorAll("canvas");
    let cards = "";
    items.forEach((it, i) => {
      const url = canvases[i]?.toDataURL("image/png");
      if (url) cards += labelHtml(it, url);
    });
    openPrint(cards, "Étiquettes QR — ZoneClimate");
  };

  const printOne = (it, i) => {
    if (!gridRef.current) return;
    const canvases = gridRef.current.querySelectorAll("canvas");
    const url = canvases[i]?.toDataURL("image/png");
    if (!url) return;
    openPrint(labelHtml(it, url), `QR ${it.code} — ZoneClimate`);
  };

  return (
    <div className="border border-border/60 bg-[#FFFFFF] rounded-lg" data-testid="catalog-manager">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-6 border-b border-border/50">
        <div>
          <p className="overline text-zinc-500">Étiquettes produits</p>
          <h2 className="font-display text-2xl font-bold tracking-tight mt-1 flex items-center gap-2">
            <QrCode weight="duotone" size={24} className="text-heat" /> Catalogue QR
          </h2>
          <p className="text-sm text-zinc-500 mt-1">
            Générez un QR code par appareil réel, imprimez-le et collez-le sur le produit. Le client scannera ce QR pour l'associer sans erreur.
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button data-testid="catalog-discover-btn" onClick={discover} disabled={scanning}
            className="rounded-full bg-heat text-white hover:bg-heat-soft font-semibold">
            {scanning ? <CircleNotch size={16} className="animate-spin mr-2" /> : <MagnifyingGlass weight="bold" size={16} className="mr-2" />}
            {scanning ? "Recherche…" : "Rechercher mes appareils"}
          </Button>
          <Button data-testid="catalog-print-btn" onClick={printLabels} disabled={items.length === 0}
            variant="outline" className="rounded-full border-border/70 font-semibold">
            <Printer weight="bold" size={16} className="mr-2" /> Imprimer
          </Button>
        </div>
      </div>

      <div className="p-6" ref={gridRef}>
        {loading && <div className="flex items-center gap-2 text-zinc-500 py-6"><CircleNotch size={18} className="animate-spin text-heat" /> Chargement…</div>}
        {!loading && items.length === 0 && (
          <p className="text-sm text-zinc-500 py-6 text-center">
            Aucun appareil au catalogue. Ajoutez d'abord vos appareils dans l'app (compte lié au projet cloud), puis cliquez « Rechercher mes appareils ».
          </p>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {items.map((it, idx) => (
            <div key={it.id} data-testid={`catalog-item-${it.code}`} className="rounded-lg border border-border/60 p-4 flex flex-col items-center text-center">
              <div className="bg-white p-2 rounded-md border border-border/40">
                <QRCodeCanvas value={it.qr} size={120} level="M" includeMargin={false} />
              </div>
              <div className="flex items-center gap-1.5 mt-3 text-xs font-semibold text-zinc-700">
                {it.category === "gainable" ? <Wind size={14} className="text-cool" /> : <Thermometer size={14} className="text-heat" />}
                <span className="truncate max-w-[130px]">{it.name}</span>
              </div>
              <span className="font-mono-num text-[11px] text-zinc-500 mt-1">{it.code}</span>
              {it.project_name && (
                <span className="mt-1 text-[10px] text-zinc-400 truncate max-w-[130px]">{it.project_name}</span>
              )}
              {it.assigned && (
                <span className="mt-2 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-online/15 text-online flex items-center gap-1">
                  <CheckCircle weight="fill" size={11} /> Associé
                </span>
              )}
              <button
                data-testid={`catalog-print-one-${it.code}`}
                onClick={() => printOne(it, idx)}
                className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-border/70 px-3 py-1.5 text-[11px] font-semibold text-zinc-700 hover:border-heat hover:text-heat transition-colors duration-200"
              >
                <Printer weight="bold" size={13} /> Imprimer ce QR
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
