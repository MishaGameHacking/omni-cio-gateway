import { Component, type ErrorInfo, type ReactNode } from "react";
import { StatePanel } from "../design-system/components";

interface Props {
  children: ReactNode;
}

interface State {
  failed: boolean;
}

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    if (import.meta.env.DEV) {
      console.error("WP17_RENDER_BOUNDARY", error.name, info.componentStack);
    }
  }

  render(): ReactNode {
    if (this.state.failed) {
      return (
        <main className="shell-fatal" role="main">
          <StatePanel
            tone="error"
            title="Интерфейс временно недоступен"
            description="Ошибка локализована в Web-слое. Финансовые действия не выполнялись."
          />
        </main>
      );
    }
    return this.props.children;
  }
}
