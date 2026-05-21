import { CheckCircle2, Info, XCircle } from "lucide-react";
import { useEffect } from "react";
import type { ToastState } from "../types";

type ToastProps = {
  toast: ToastState;
  onClose: () => void;
};

export function Toast({ toast, onClose }: ToastProps) {
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(onClose, 4200);
    return () => window.clearTimeout(timer);
  }, [toast, onClose]);

  if (!toast) return null;
  const Icon = toast.tone === "success" ? CheckCircle2 : toast.tone === "danger" ? XCircle : Info;
  return (
    <div className={`toast ${toast.tone}`} role="status">
      <Icon size={20} />
      <span>{toast.message}</span>
      <button type="button" onClick={onClose} aria-label="关闭通知">
        关闭
      </button>
    </div>
  );
}
