import type { ReactNode } from "react";
import { useEffect, useRef } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  eyebrow: string;
  title: string;
  children: ReactNode;
  wide?: boolean;
}

export default function Modal({ open, onClose, eyebrow, title, children, wide }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={onClose}
      style={wide ? { width: "min(760px, calc(100vw - 40px))" } : undefined}
    >
      <div className="modal-heading">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h2>{title}</h2>
        </div>
        <button type="button" className="close-button" onClick={onClose} aria-label="关闭">
          ×
        </button>
      </div>
      {open && children}
    </dialog>
  );
}
