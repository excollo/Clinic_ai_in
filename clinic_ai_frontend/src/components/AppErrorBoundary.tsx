import { Component, type ErrorInfo, type ReactNode } from "react";
import i18n from "@/i18n";

type Props = { children: ReactNode };
type State = { hasError: boolean };

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("appErrorBoundary", error, info);
  }

  render() {
    if (this.state.hasError) {
      return <div className="grid min-h-screen place-items-center text-sm">{i18n.t("errors.boundary_fallback")}</div>;
    }
    return this.props.children;
  }
}
