import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "@/shared/lib/auth";
import { errMsg } from "@/shared/lib/utils";
import { Button, Field, Input } from "@/shared/ui/primitives";
import { AuthLayout } from "./AuthLayout";

export default function Register() {
  const { register, user } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", org_name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await register({ ...form, org_name: form.org_name || undefined });
      nav("/", { replace: true });
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout title="Create your workspace" subtitle="You'll get an organization, a starter project and a ready-made agent library.">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Your name">
          <Input required autoComplete="name" value={form.name} onChange={set("name")} placeholder="Ada Lovelace" />
        </Field>
        <Field label="Work email">
          <Input type="email" required autoComplete="email" value={form.email} onChange={set("email")} placeholder="you@company.com" />
        </Field>
        <Field label="Password" hint="At least 8 characters with a mix of letters, numbers or symbols.">
          <Input type="password" required minLength={8} autoComplete="new-password" value={form.password} onChange={set("password")} />
        </Field>
        <Field label="Organization name (optional)">
          <Input value={form.org_name} onChange={set("org_name")} placeholder="Acme Inc." />
        </Field>
        {error && <div className="rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2 text-sm text-danger">{error}</div>}
        <Button type="submit" size="lg" className="w-full justify-center" loading={busy}>
          Create account
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        Already have an account?{" "}
        <Link to="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
