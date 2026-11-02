import type { LucideIcon } from "lucide-react";

export default function StatCard({ label, value, detail, icon: Icon, tone }: {
  label: string;
  value: number | string;
  detail: string;
  icon: LucideIcon;
  tone: "blue" | "teal" | "amber" | "green";
}) {
  const tones = {
    blue: "bg-blue-50 text-blue-700",
    teal: "bg-teal-50 text-teal-700",
    amber: "bg-amber-50 text-amber-700",
    green: "bg-emerald-50 text-emerald-700",
  };
  return <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card">
    <div className="flex items-start justify-between">
      <div><p className="text-sm font-medium text-slate-500">{label}</p><p className="mt-3 text-[32px] font-bold leading-none tracking-tight text-ink">{value}</p></div>
      <div className={`grid h-11 w-11 place-items-center rounded-xl ${tones[tone]}`}><Icon size={20} /></div>
    </div>
    <p className="mt-4 text-xs text-slate-500">{detail}</p>
  </article>;
}
