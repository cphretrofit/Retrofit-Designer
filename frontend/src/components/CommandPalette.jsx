import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CommandDialog, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem, CommandSeparator,
} from "@/components/ui/command";
import { getProjects } from "@/lib/api";
import {
  LayoutDashboard, Plus, Camera, Calculator, FileText, GitBranch, ScanSearch,
  ListChecks, FolderOpen, ArrowRight, Building2,
} from "lucide-react";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [projects, setProjects] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    const down = (e) => {
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    const openEvt = () => setOpen(true);
    document.addEventListener("keydown", down);
    window.addEventListener("open-command-palette", openEvt);
    return () => {
      document.removeEventListener("keydown", down);
      window.removeEventListener("open-command-palette", openEvt);
    };
  }, []);

  useEffect(() => {
    if (open && projects.length === 0) getProjects().then(setProjects).catch(() => {});
  }, [open, projects.length]);

  const go = (path) => { setOpen(false); navigate(path); };
  const hero = "RTF-2026-0142";

  const actions = [
    { icon: Plus, label: "Add Measure", hint: "New EEM", run: () => go(`/project/${hero}/design/measure-EWI`) },
    { icon: Camera, label: "Add Photograph", hint: "Survey", run: () => go(`/project/${hero}/design/photos`) },
    { icon: Calculator, label: "Open Calculations", run: () => go(`/project/${hero}/design/calculations`) },
    { icon: FileText, label: "Open EWI Specification", run: () => go(`/project/${hero}/design/measure-EWI`) },
    { icon: ListChecks, label: "Run Design Check", run: () => go(`/project/${hero}/design/design-review`) },
    { icon: FolderOpen, label: "Generate Design Pack", run: () => go(`/project/${hero}/pack`) },
    { icon: GitBranch, label: "Search Details", run: () => go(`/project/${hero}/design/junctions`) },
    { icon: ScanSearch, label: "Go to Outstanding Items", run: () => go(`/project/${hero}/design/outstanding`) },
  ];

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Search actions, projects, details…" />
      <CommandList className="thin-scroll">
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigate">
          <CommandItem onSelect={() => go("/")}>
            <LayoutDashboard className="mr-2 h-4 w-4" strokeWidth={1.5} />
            Command Centre
          </CommandItem>
        </CommandGroup>
        <CommandGroup heading="Actions">
          {actions.map((a) => (
            <CommandItem key={a.label} onSelect={a.run}>
              <a.icon className="mr-2 h-4 w-4" strokeWidth={1.5} />
              <span>{a.label}</span>
              {a.hint && <span className="ml-auto text-[11px] text-muted-foreground font-mono">{a.hint}</span>}
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Projects">
          {projects.map((p) => (
            <CommandItem key={p.id} onSelect={() => go(`/project/${p.id}`)}>
              <Building2 className="mr-2 h-4 w-4" strokeWidth={1.5} />
              <span>{p.name}</span>
              <span className="ml-auto text-[11px] text-muted-foreground font-mono">{p.ref}</span>
              <ArrowRight className="ml-2 h-3.5 w-3.5 text-muted-foreground" strokeWidth={1.5} />
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
