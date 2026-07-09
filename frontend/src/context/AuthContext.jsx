import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api, { setToken } from "../lib/api";

const AuthContext = createContext(null);

export const ROLE_LABELS = {
  super_admin: "Super Admin",
  moderator: "Modérateur",
  installer: "Installateur",
  client: "Client",
  guest: "Invité",
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=checking, false=anon, object=user

  const refresh = useCallback(async () => {
    try {
      const u = await api.me();
      setUser(u);
    } catch {
      setUser(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = async (email, password) => {
    const data = await api.login({ email, password });
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  };

  const register = async (payload) => {
    const data = await api.register(payload);
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try { await api.logout(); } catch {}
    setToken(null);
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
