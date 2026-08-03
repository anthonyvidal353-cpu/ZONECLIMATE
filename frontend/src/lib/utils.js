import { clsx } from "clsx";
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

// Affiche une température réelle, ou « — » si la mesure est indisponible (thermostat hors ligne / non configuré).
export function fmtTemp(t, digits = 1) {
  if (t === null || t === undefined || Number.isNaN(Number(t))) return "—";
  return Number(t).toFixed(digits);
}
