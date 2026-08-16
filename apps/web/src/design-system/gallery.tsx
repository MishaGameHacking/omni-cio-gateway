import { Button, Card, ChartFrame, DataTable, DialogExample, DrawerExample, Field, RiskBadge, Skeleton, StatePanel, StatusBadge, Toast } from "./components";
import { operationalStates, riskSeverities } from "./contracts";

export function DesignSystemGallery() {
  return <main className="ds-page" data-testid="component-matrix">
    <header className="ds-hero"><p className="ds-eyebrow">WP16 · Design System</p><h1>Omni-CIO Design System</h1><p>Единый mobile-first UI-фундамент. Только синтетические демонстрационные данные.</p></header>
    <section className="ds-grid" aria-label="Компоненты дизайн-системы">
      <Card title="Typography & actions"><p className="ds-lead">Финансовая информация должна быть читаемой и проверяемой.</p><div className="ds-row"><Button>Основное действие</Button><Button variant="secondary">Вторичное</Button><Button variant="danger">Опасное</Button></div></Card>
      <Card title="Operational states"><div className="ds-row ds-row--wrap">{operationalStates.map((state) => <StatusBadge key={state} state={state} />)}</div></Card>
      <Card title="Risk severity"><div className="ds-row ds-row--wrap">{riskSeverities.map((risk) => <RiskBadge key={risk} severity={risk} />)}</div></Card>
      <Card title="Forms"><Field id="design-token-example" label="Подпись поля" placeholder="Без секретов" /><p className="ds-hint">Browser storage для credentials запрещён.</p></Card>
      <Card title="Table"><DataTable caption="Синтетический пример" headers={["Объект", "Состояние", "Значение"]} rows={[["Строка A", "READY", "100,00"], ["Строка B", "STALE", "—"]]} /></Card>
      <Card title="Chart wrapper"><ChartFrame title="Синтетический ряд"><div className="ds-bars" aria-hidden="true"><span className="ds-bar--42" /><span className="ds-bar--72" /><span className="ds-bar--58" /><span className="ds-bar--84" /></div></ChartFrame></Card>
      <Card title="Feedback states"><div className="ds-stack"><StatePanel kind="warning" title="STALE">Данные требуют обновления.</StatePanel><StatePanel kind="error" title="ERROR">Действие заблокировано.</StatePanel><StatePanel kind="empty" title="EMPTY">Данных пока нет.</StatePanel><Toast>Неблокирующее системное сообщение.</Toast></div></Card>
      <Card title="Loading"><Skeleton /><Skeleton label="Загрузка таблицы" /></Card>
      <Card title="Dialog & drawer"><div className="ds-stack"><DialogExample /><DrawerExample /></div></Card>
      <Card title="Theme tokens"><div className="ds-theme-samples"><div className="ds-theme-sample" data-theme="light">Light</div><div className="ds-theme-sample" data-theme="dark">Dark</div></div></Card>
    </section>
  </main>;
}