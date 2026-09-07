import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/context/ThemeProvider";
import { AuthProvider } from "@/context/AuthContext";
import { ProtectedRoute, AdminRoute } from "@/components/ProtectedRoute";
import { CommandPalette } from "@/components/CommandPalette";
import { Toaster } from "@/components/ui/sonner";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import ProjectOverview from "@/pages/ProjectOverview";
import DesignWorkspace from "@/pages/DesignWorkspace";
import DesignPack from "@/pages/DesignPack";
import ImportProject from "@/pages/ImportProject";
import Templates from "@/pages/Templates";
import Clients from "@/pages/Clients";
import ClientDetail from "@/pages/ClientDetail";
import UserManagement from "@/pages/UserManagement";
import Maintenance from "@/pages/Maintenance";
import ChangePassword from "@/pages/ChangePassword";
import PublicWalkthrough from "@/pages/PublicWalkthrough";

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <Toaster position="bottom-right" />
          <CommandPalette />
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/w/:token" element={<PublicWalkthrough />} />
            <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/import" element={<ProtectedRoute><ImportProject /></ProtectedRoute>} />
            <Route path="/templates" element={<ProtectedRoute><Templates /></ProtectedRoute>} />
            <Route path="/clients" element={<ProtectedRoute><Clients /></ProtectedRoute>} />
            <Route path="/clients/:id" element={<ProtectedRoute><ClientDetail /></ProtectedRoute>} />
            <Route path="/project/:id" element={<ProtectedRoute><ProjectOverview /></ProtectedRoute>} />
            <Route path="/project/:id/design" element={<ProtectedRoute><DesignWorkspace /></ProtectedRoute>} />
            <Route path="/project/:id/design/:section" element={<ProtectedRoute><DesignWorkspace /></ProtectedRoute>} />
            <Route path="/project/:id/pack" element={<ProtectedRoute><DesignPack /></ProtectedRoute>} />
            <Route path="/users" element={<AdminRoute><UserManagement /></AdminRoute>} />
            <Route path="/maintenance" element={<AdminRoute><Maintenance /></AdminRoute>} />
            <Route path="/account/password" element={<ProtectedRoute><ChangePassword /></ProtectedRoute>} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
