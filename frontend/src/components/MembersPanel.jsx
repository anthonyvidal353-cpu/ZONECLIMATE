import { useEffect, useState, useCallback } from "react";
import { UserPlus, Copy, ShieldCheck, Crown, User, Wrench } from "@phosphor-icons/react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "../lib/api";
import { useAuth, ROLE_LABELS } from "../context/AuthContext";
import { Button } from "./ui/button";
import { Switch } from "./ui/switch";

const RELATION_ICON = (relation) => {
  if (relation?.startsWith("Propriétaire")) return <Crown weight="fill" size={18} className="text-amber-400" />;
  if (relation?.startsWith("Installateur")) return <Wrench weight="duotone" size={18} className="text-cool" />;
  return <User weight="duotone" size={18} className="text-zinc-600" />;
};

export const MembersPanel = ({ installation, onUpdated }) => {
  const { user } = useAuth();
  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [lastCode, setLastCode] = useState(null);

  const isOwner = installation.owner_id === user.id;
  const isInstaller = installation.installer_id === user.id;
  const isAdmin = user.role === "super_admin";
  const canInviteClient = isAdmin || isInstaller;
  const canInviteGuest = isAdmin || isOwner;

  const load = useCallback(async () => {
    const [m, inv] = await Promise.all([
      api.members(installation.id),
      api.listInvites(installation.id).catch(() => []),
    ]);
    setMembers(m);
    setInvites(inv);
  }, [installation.id]);

  useEffect(() => { load(); }, [load]);

  const invite = async (role) => {
    try {
      const res = await api.invite(installation.id, role);
      setLastCode({ code: res.code, role });
      toast.success(`Invitation ${role === "client" ? "client (maître)" : "invité"} créée`);
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const toggleInstallerAccess = async () => {
    try {
      const updated = await api.updateInstallation(installation.id, { installer_access: !installation.installer_access });
      toast(updated.installer_access ? "Accès installateur activé" : "Accès installateur révoqué");
      onUpdated?.(updated);
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const copy = (code) => {
    navigator.clipboard?.writeText(code);
    toast.success("Code copié");
  };

  return (
    <div className="space-y-6">
      {/* Members */}
      <div className="border border-border/60 bg-[#FFFFFF] rounded-lg">
        <div className="p-6 border-b border-border/50">
          <p className="overline text-zinc-500">Accès à l'installation</p>
          <h2 className="font-display text-2xl font-bold tracking-tight mt-1">Membres</h2>
        </div>
        <div className="divide-y divide-border/40">
          {members.map((m) => (
            <div key={m.id} data-testid={`member-${m.id}`} className="flex items-center justify-between p-4 md:px-6">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-md border border-border/60 flex items-center justify-center">
                  {RELATION_ICON(m.relation)}
                </div>
                <div>
                  <p className="font-medium text-sm">{m.name} <span className="text-zinc-500 font-normal">· {m.email}</span></p>
                  <p className="text-xs text-zinc-500">{m.relation} · {ROLE_LABELS[m.role]}</p>
                </div>
              </div>
              {m.relation?.startsWith("Installateur") && (isOwner || isAdmin) && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-500 hidden sm:inline">Accès</span>
                  <Switch data-testid="installer-access-toggle" checked={installation.installer_access} onCheckedChange={toggleInstallerAccess} />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Invitations */}
      {(canInviteClient || canInviteGuest) && (
        <div className="border border-border/60 bg-[#FFFFFF] rounded-lg p-6">
          <p className="overline text-zinc-500">Inviter</p>
          <h2 className="font-display text-2xl font-bold tracking-tight mt-1 mb-4">Ajouter un utilisateur</h2>

          <div className="flex flex-wrap gap-3">
            {canInviteClient && !installation.owner_id && (
              <Button data-testid="invite-client-btn" onClick={() => invite("client")} className="rounded-full bg-heat text-black hover:bg-heat-soft font-semibold">
                <Crown weight="fill" size={16} className="mr-2" /> Inviter un client (maître)
              </Button>
            )}
            {canInviteClient && installation.owner_id && (
              <p className="text-sm text-zinc-500">Cette installation a déjà un propriétaire (maître) : {installation.owner_name}.</p>
            )}
            {canInviteGuest && (
              <Button data-testid="invite-guest-btn" onClick={() => invite("guest")} variant="outline" className="rounded-full border-border/70 font-semibold">
                <UserPlus weight="bold" size={16} className="mr-2" /> Inviter un invité (lecture)
              </Button>
            )}
          </div>

          {lastCode && (
            <div data-testid="invite-code-box" className="mt-4 flex items-center justify-between rounded-md border border-heat/40 bg-heat/10 px-4 py-3">
              <div>
                <p className="text-xs text-zinc-600">Code d'invitation ({lastCode.role === "client" ? "client / maître" : "invité"})</p>
                <p className="font-mono-num text-2xl font-bold text-heat tracking-widest">{lastCode.code}</p>
              </div>
              <button onClick={() => copy(lastCode.code)} className="text-zinc-700 hover:text-zinc-900 transition-colors duration-200">
                <Copy size={20} />
              </button>
            </div>
          )}

          {invites.filter((i) => i.status === "pending").length > 0 && (
            <div className="mt-5">
              <p className="overline text-zinc-500 mb-2">Invitations en attente</p>
              <div className="space-y-1">
                {invites.filter((i) => i.status === "pending").map((i) => (
                  <div key={i.id} className="flex items-center justify-between text-sm rounded px-3 py-2 bg-zinc-50 border border-border/50">
                    <span className="font-mono-num font-semibold tracking-widest">{i.code}</span>
                    <span className="text-zinc-500">{i.role === "client" ? "Client (maître)" : "Invité"}</span>
                    <button onClick={() => copy(i.code)} className="text-zinc-600 hover:text-zinc-900"><Copy size={16} /></button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
