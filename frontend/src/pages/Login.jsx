import { useState } from "react";
import { Thermometer, Envelope, Lock, User } from "@phosphor-icons/react";
import { motion } from "framer-motion";
import { useAuth } from "../context/AuthContext";
import { formatApiErrorDetail } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";

export default function Login() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState("login"); // login | register
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("client");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "login") {
        await login(email, password);
        toast.success("Connexion réussie");
      } else {
        await register({ email, password, name, role });
        toast.success("Compte créé");
      }
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setBusy(false);
    }
  };

  const demoAccounts = [
    ["Super Admin", "admin@climazone.fr", "Admin1234!"],
    ["Installateur", "installateur@demo.fr", "Demo1234!"],
    ["Client (Maître)", "client@demo.fr", "Demo1234!"],
    ["Invité", "invite@demo.fr", "Demo1234!"],
  ];

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">
      {/* Left brand panel */}
      <div className="relative hidden lg:flex flex-col justify-between p-12 border-r border-border/50 overflow-hidden">
        <div aria-hidden="true" className="absolute -bottom-40 -left-20 w-96 h-96 rounded-full blur-[130px] opacity-20 bg-heat" />
        <div className="relative flex items-center gap-3">
          <div className="w-10 h-10 rounded-md bg-heat/15 border border-heat/30 flex items-center justify-center">
            <Thermometer weight="fill" size={22} className="text-heat" />
          </div>
          <span className="font-display font-extrabold tracking-tighter text-xl">ClimaZone</span>
        </div>
        <div className="relative">
          <p className="overline text-zinc-500 mb-4">Pilotage Gainable Connecté</p>
          <h1 className="font-display text-5xl font-extrabold tracking-tighter leading-[1.05]">
            Votre installation,<br />zone par zone.
          </h1>
          <p className="text-zinc-400 mt-5 max-w-md">
            Centralisez votre gainable et vos thermostats connectés. Un thermostat maître
            pilote le mode chaud/froid, chaque zone garde sa consigne.
          </p>
        </div>
        <div className="relative rounded-lg border border-border/60 bg-[#121212] p-4">
          <p className="overline text-zinc-500 mb-2">Comptes de démonstration</p>
          <div className="space-y-1">
            {demoAccounts.map(([label, mail, pw]) => (
              <button
                key={mail}
                onClick={() => { setMode("login"); setEmail(mail); setPassword(pw); }}
                data-testid={`demo-${mail}`}
                className="w-full flex items-center justify-between text-xs rounded px-2 py-1.5 hover:bg-white/5 transition-colors duration-200"
              >
                <span className="text-zinc-300">{label}</span>
                <span className="font-mono-num text-zinc-500">{mail}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right form */}
      <div className="flex items-center justify-center p-6">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-sm">
          <h2 className="font-display text-3xl font-extrabold tracking-tighter">
            {mode === "login" ? "Connexion" : "Créer un compte"}
          </h2>
          <p className="text-sm text-zinc-500 mt-1">
            {mode === "login" ? "Accédez à votre espace ClimaZone." : "Rejoignez ClimaZone en tant qu'installateur ou client."}
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            {mode === "register" && (
              <div>
                <Label className="text-xs text-zinc-400">Nom complet</Label>
                <div className="relative mt-1">
                  <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                  <Input data-testid="name-input" value={name} onChange={(e) => setName(e.target.value)} required className="pl-9 bg-black/40 border-border/70" placeholder="Jean Dupont" />
                </div>
              </div>
            )}
            <div>
              <Label className="text-xs text-zinc-400">Email</Label>
              <div className="relative mt-1">
                <Envelope size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                <Input data-testid="email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="pl-9 bg-black/40 border-border/70" placeholder="vous@exemple.fr" />
              </div>
            </div>
            <div>
              <Label className="text-xs text-zinc-400">Mot de passe</Label>
              <div className="relative mt-1">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                <Input data-testid="password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className="pl-9 bg-black/40 border-border/70" placeholder="••••••••" />
              </div>
            </div>
            {mode === "register" && (
              <div>
                <Label className="text-xs text-zinc-400">Je suis</Label>
                <div className="flex gap-2 mt-1">
                  {[["client", "Client"], ["installer", "Installateur"]].map(([val, lbl]) => (
                    <button key={val} type="button" data-testid={`role-${val}`} onClick={() => setRole(val)}
                      className="flex-1 rounded-md border py-2 text-sm font-semibold transition-colors duration-200"
                      style={{ borderColor: role === val ? "#FF5722" : "#27272A", background: role === val ? "rgba(255,87,34,0.12)" : "transparent", color: role === val ? "#FF5722" : "#A1A1AA" }}>
                      {lbl}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {error && <p data-testid="auth-error" className="text-sm text-offline">{error}</p>}

            <Button data-testid="submit-btn" type="submit" disabled={busy} className="w-full rounded-full bg-heat text-black hover:bg-heat-soft font-semibold h-11">
              {busy ? "Veuillez patienter…" : mode === "login" ? "Se connecter" : "Créer mon compte"}
            </Button>
          </form>

          <p className="text-sm text-zinc-500 mt-6 text-center">
            {mode === "login" ? "Pas encore de compte ?" : "Déjà inscrit ?"}{" "}
            <button data-testid="toggle-mode" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }} className="text-heat font-semibold hover:underline">
              {mode === "login" ? "Créer un compte" : "Se connecter"}
            </button>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
