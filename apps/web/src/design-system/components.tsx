import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import type { OperationalState, RiskSeverity } from "./contracts";

export function Card({ title, children }: { title: string; children: ReactNode }) {
  return <section className="ds-card"><h2 className="ds-card__title">{title}</h2>{children}</section>;
}

export function Button({ variant = "primary", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  return <button className={`ds-button ds-button--${variant}`} type="button" {...props} />;
}

export function StatusBadge({ state }: { state: OperationalState }) {
  return <span className="ds-badge" data-state={state}>{state}</span>;
}

export function RiskBadge({ severity }: { severity: RiskSeverity }) {
  return <span className="ds-risk" data-risk={severity}>Риск: {severity}</span>;
}

export function Field({ label, id, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; id: string }) {
  return <label className="ds-field" htmlFor={id}><span>{label}</span><input className="ds-input" id={id} {...props} /></label>;
}

export function DataTable({ caption, headers, rows }: { caption: string; headers: string[]; rows: string[][] }) {
  return <div className="ds-table-wrap"><table className="ds-table"><caption>{caption}</caption><thead><tr>{headers.map((header) => <th key={header} scope="col">{header}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={`${caption}-${index}`}>{row.map((cell, cellIndex) => <td key={`${index}-${cellIndex}`}>{cell}</td>)}</tr>)}</tbody></table></div>;
}

export function StatePanel({ kind, title, children }: { kind: "empty" | "error" | "warning"; title: string; children: ReactNode }) {
  return <div className="ds-state" data-kind={kind} role={kind === "error" ? "alert" : "status"}><strong>{title}</strong><span>{children}</span></div>;
}

export function Skeleton({ label = "Загрузка" }: { label?: string }) {
  return <div className="ds-skeleton" role="status" aria-label={label}><span aria-hidden="true" /></div>;
}

export function Toast({ children }: { children: ReactNode }) {
  return <div className="ds-toast" role="status" aria-live="polite">{children}</div>;
}

export function DialogExample() {
  return <div className="ds-dialog" role="dialog" aria-modal="false" aria-labelledby="dialog-title"><strong id="dialog-title">Диалог подтверждения</strong><p>Без финансового действия в WP16.</p><Button variant="secondary">Закрыть</Button></div>;
}

export function DrawerExample() {
  return <aside className="ds-drawer" aria-label="Пример панели"><strong>Drawer</strong><p>Компонент-контейнер без navigation/business flow.</p></aside>;
}

export function ChartFrame({ title, children }: { title: string; children: ReactNode }) {
  return <figure className="ds-chart" aria-label={title}><figcaption>{title}</figcaption><div className="ds-chart__plot">{children}</div></figure>;
}
