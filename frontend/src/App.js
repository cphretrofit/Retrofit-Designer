import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/context/ThemeProvider";
import { CommandPalette } from "@/components/CommandPalette";
import { Toaster } from "@/components/ui/sonner";
import Dashboard from "@/pages/Dashboard";
import ProjectOverview from "@/pages/ProjectOverview";
import DesignWorkspace from "@/pages/DesignWorkspace";
import DesignPack from "@/pages/DesignPack";
import ImportProject from "@/pages/ImportProject";

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <CommandPalette />
        <Toaster position="bottom-right" />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/import" element={<ImportProject />} />
          <Route path="/project/:id" element={<ProjectOverview />} />
          <Route path="/project/:id/design" element={<DesignWorkspace />} />
          <Route path="/project/:id/design/:section" element={<DesignWorkspace />} />
          <Route path="/project/:id/pack" element={<DesignPack />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
