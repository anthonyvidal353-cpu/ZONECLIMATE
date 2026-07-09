import { Couch, ForkKnife, Bed, Baby, Desktop, Shower, House, Thermometer } from "@phosphor-icons/react";

export const zoneIcons = {
  couch: Couch,
  fork: ForkKnife,
  bed: Bed,
  baby: Baby,
  desktop: Desktop,
  shower: Shower,
  house: House,
};

export function ZoneIcon({ name, ...props }) {
  const Cmp = zoneIcons[name] || Thermometer;
  return <Cmp {...props} />;
}

export const DAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
export const DAYS_FULL = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];
