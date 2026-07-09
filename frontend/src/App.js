import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { Thermometer } from "@phosphor-icons/react";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Login from "@/pages/Login";
import Home from "@/pages/Home";
import InstallationDashboard from "@/pages/InstallationDashboard";

function Splash() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="flex items-center gap-3 text-zinc-400">
        <Thermometer size={22} className="animate-pulse text-heat" />
        <span className="font-display">ZoneClimate…</span>
      </div>
    </div>
  );
}

function Protected({ children }) {
  const { user } = useAuth();
  if (user === null) return <Splash />;
  if (user === false) return <Navigate to="/login" replace />;
  return children;
}

function LoginRoute() {
  const { user } = useAuth();
  if (user === null) return <Splash />;
  if (user) return <Navigate to="/" replace />;
  return <Login />;
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <Toaster theme="dark" position="top-right" richColors />
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginRoute />} />
            <Route path="/" element={<Protected><Home /></Protected>} />
            <Route path="/installations/:id" element={<Protected><InstallationDashboard /></Protected>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
