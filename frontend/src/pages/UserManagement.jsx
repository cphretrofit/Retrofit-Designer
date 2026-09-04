import { useEffect, useState } from "react";
import { TopBar } from "@/components/Shell";
import { useAuth, formatApiError } from "@/context/AuthContext";
import { AdminTabs } from "@/components/AdminTabs";
import { listUsers, createUser, updateUser, resetUserPassword, deleteUser } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Loader2, Pencil, KeyRound, Trash2, ShieldCheck, User as UserIcon, X } from "lucide-react";

const empty = { name: "", email: "", password: "", role: "user" };

function Modal({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-md bg-card border border-border rounded-md shadow-xl" onClick={(e) => e.stopPropagation()} data-testid="user-modal">
        <div className="flex items-center justify-between px-5 h-12 border-b border-border">
          <div className="font-medium text-[14px]">{title}</div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground" data-testid="modal-close"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

const inputCls = "w-full h-10 px-3 bg-background border border-border rounded-sm text-[13px] outline-none focus:border-foreground/40 transition-colors";
const labelCls = "block text-[11px] uppercase tracking-[0.12em] text-muted-foreground mb-1.5 mt-3 first:mt-0";

export default function UserManagement() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState(null);
  const [modal, setModal] = useState(null); // {mode:'create'|'edit'|'reset'|'delete', user}
  const [form, setForm] = useState(empty);
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => listUsers().then(setUsers).catch((e) => toast.error(formatApiError(e.response?.data?.detail)));
  useEffect(() => { load(); }, []);

  const openCreate = () => { setForm(empty); setModal({ mode: "create" }); };
  const openEdit = (u) => { setForm({ name: u.name, email: u.email, role: u.role }); setModal({ mode: "edit", user: u }); };
  const openReset = (u) => { setPw(""); setModal({ mode: "reset", user: u }); };
  const openDelete = (u) => setModal({ mode: "delete", user: u });
  const close = () => setModal(null);

  const err = (e) => toast.error(formatApiError(e.response?.data?.detail) || "Action failed");

  const submitCreate = async () => {
    setBusy(true);
    try { await createUser(form); toast.success("User created"); close(); load(); }
    catch (e) { err(e); } finally { setBusy(false); }
  };
  const submitEdit = async () => {
    setBusy(true);
    try { await updateUser(modal.user.id, form); toast.success("User updated"); close(); load(); }
    catch (e) { err(e); } finally { setBusy(false); }
  };
  const toggleActive = async (u) => {
    try { await updateUser(u.id, { is_active: !u.is_active }); toast.success(u.is_active ? "User deactivated" : "User activated"); load(); }
    catch (e) { err(e); }
  };
  const submitReset = async () => {
    setBusy(true);
    try { await resetUserPassword(modal.user.id, pw); toast.success("Password reset"); close(); }
    catch (e) { err(e); } finally { setBusy(false); }
  };
  const submitDelete = async () => {
    setBusy(true);
    try { await deleteUser(modal.user.id); toast.success("User deleted"); close(); load(); }
    catch (e) { err(e); } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <TopBar crumbs={[{ label: "Command Centre", to: "/" }, { label: "User Management" }]} />
      <main className="max-w-5xl mx-auto px-6 py-10">
        <AdminTabs />
        <div className="flex items-end justify-between">
          <div>
            <h1 className="font-display font-300 text-4xl tracking-tight">User Management</h1>
            <div className="text-sm text-muted-foreground mt-1.5">Create, edit and manage who can access the platform.</div>
          </div>
          <button onClick={openCreate} data-testid="add-user-btn" className="flex items-center gap-2 h-9 px-3.5 bg-primary text-primary-foreground rounded-sm text-[13px] font-medium hover:opacity-90 transition-opacity">
            <Plus className="h-4 w-4" strokeWidth={1.75} /> Add user
          </button>
        </div>

        <div className="mt-8 border border-border rounded-md overflow-hidden">
          <div className="grid grid-cols-12 px-4 h-10 items-center text-[10px] uppercase tracking-[0.1em] text-muted-foreground bg-secondary/40 border-b border-border">
            <div className="col-span-4">Name</div><div className="col-span-3">Role</div><div className="col-span-2">Status</div><div className="col-span-3 text-right">Actions</div>
          </div>
          {users === null && <div className="p-8 text-center"><Loader2 className="h-4 w-4 animate-spin inline text-muted-foreground" /></div>}
          {users && users.map((u) => (
            <div key={u.id} className="grid grid-cols-12 px-4 py-3 items-center border-b border-border last:border-0" data-testid={`user-row-${u.email}`}>
              <div className="col-span-4 min-w-0">
                <div className="text-[13px] font-medium truncate">{u.name}{u.id === me?.id && <span className="text-muted-foreground font-normal"> (you)</span>}</div>
                <div className="text-[11px] text-muted-foreground font-mono truncate">{u.email}</div>
              </div>
              <div className="col-span-3">
                <span className={`inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-sm border ${u.role === "admin" ? "border-foreground/20 text-foreground" : "border-border text-muted-foreground"}`}>
                  {u.role === "admin" ? <ShieldCheck className="h-3 w-3" /> : <UserIcon className="h-3 w-3" />}{u.role === "admin" ? "Admin" : "User"}
                </span>
              </div>
              <div className="col-span-2">
                <button onClick={() => toggleActive(u)} data-testid={`toggle-active-${u.email}`} className="inline-flex items-center gap-1.5 text-[11px]">
                  <span className={`h-1.5 w-1.5 rounded-full ${u.is_active ? "bg-green-500" : "bg-neutral-400"}`} />
                  {u.is_active ? "Active" : "Inactive"}
                </button>
              </div>
              <div className="col-span-3 flex items-center justify-end gap-1">
                <button onClick={() => openEdit(u)} title="Edit" data-testid={`edit-user-${u.email}`} className="h-8 w-8 flex items-center justify-center rounded-sm hover:bg-secondary text-muted-foreground hover:text-foreground"><Pencil className="h-3.5 w-3.5" /></button>
                <button onClick={() => openReset(u)} title="Reset password" data-testid={`reset-user-${u.email}`} className="h-8 w-8 flex items-center justify-center rounded-sm hover:bg-secondary text-muted-foreground hover:text-foreground"><KeyRound className="h-3.5 w-3.5" /></button>
                <button onClick={() => openDelete(u)} title="Delete" data-testid={`delete-user-${u.email}`} className="h-8 w-8 flex items-center justify-center rounded-sm hover:bg-red-50 text-muted-foreground hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            </div>
          ))}
        </div>
      </main>

      {modal?.mode === "create" && (
        <Modal title="Add user" onClose={close}>
          <label className={labelCls}>Full name</label>
          <input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="form-name" />
          <label className={labelCls}>Email</label>
          <input className={inputCls} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="form-email" />
          <label className={labelCls}>Password</label>
          <input className={inputCls} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="form-password" />
          <label className={labelCls}>Role</label>
          <select className={inputCls} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} data-testid="form-role">
            <option value="user">User</option><option value="admin">Admin</option>
          </select>
          <button onClick={submitCreate} disabled={busy} data-testid="submit-create" className="w-full h-10 mt-5 bg-primary text-primary-foreground rounded-sm text-[13px] font-medium disabled:opacity-60">{busy ? "Creating…" : "Create user"}</button>
        </Modal>
      )}
      {modal?.mode === "edit" && (
        <Modal title={`Edit ${modal.user.name}`} onClose={close}>
          <label className={labelCls}>Full name</label>
          <input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="form-name" />
          <label className={labelCls}>Email</label>
          <input className={inputCls} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="form-email" />
          <label className={labelCls}>Role</label>
          <select className={inputCls} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} disabled={modal.user.id === me?.id} data-testid="form-role">
            <option value="user">User</option><option value="admin">Admin</option>
          </select>
          {modal.user.id === me?.id && <div className="text-[11px] text-muted-foreground mt-1.5">You cannot change your own role.</div>}
          <button onClick={submitEdit} disabled={busy} data-testid="submit-edit" className="w-full h-10 mt-5 bg-primary text-primary-foreground rounded-sm text-[13px] font-medium disabled:opacity-60">{busy ? "Saving…" : "Save changes"}</button>
        </Modal>
      )}
      {modal?.mode === "reset" && (
        <Modal title={`Reset password — ${modal.user.name}`} onClose={close}>
          <label className={labelCls}>New password</label>
          <input className={inputCls} value={pw} onChange={(e) => setPw(e.target.value)} data-testid="form-new-password" placeholder="At least 8 characters" />
          <button onClick={submitReset} disabled={busy || pw.length < 8} data-testid="submit-reset" className="w-full h-10 mt-5 bg-primary text-primary-foreground rounded-sm text-[13px] font-medium disabled:opacity-60">{busy ? "Resetting…" : "Reset password"}</button>
        </Modal>
      )}
      {modal?.mode === "delete" && (
        <Modal title="Delete user" onClose={close}>
          <div className="text-[13px]">Delete <span className="font-medium">{modal.user.name}</span> ({modal.user.email})? This cannot be undone.</div>
          <div className="flex gap-2 mt-6">
            <button onClick={close} className="flex-1 h-10 border border-border rounded-sm text-[13px]">Cancel</button>
            <button onClick={submitDelete} disabled={busy} data-testid="confirm-delete" className="flex-1 h-10 bg-red-600 text-white rounded-sm text-[13px] font-medium disabled:opacity-60">{busy ? "Deleting…" : "Delete"}</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
