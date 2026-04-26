import * as RDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  children: ReactNode;
}

export function Dialog({ open, onOpenChange, title, description, children }: DialogProps) {
  return (
    <RDialog.Root open={open} onOpenChange={onOpenChange}>
      <RDialog.Portal>
        <RDialog.Overlay className="fixed inset-0 bg-black/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <RDialog.Content className="fixed left-1/2 top-1/2 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-card border border-border bg-surface p-6 shadow-xl">
          <div className="flex items-start justify-between gap-4">
            <div>
              {title && <RDialog.Title className="text-lg font-semibold">{title}</RDialog.Title>}
              {description && (
                <RDialog.Description className="mt-1 text-sm text-text-secondary">
                  {description}
                </RDialog.Description>
              )}
            </div>
            <RDialog.Close className="rounded-input p-1 text-text-secondary hover:bg-bg" aria-label="Close">
              <X size={16} />
            </RDialog.Close>
          </div>
          <div className="mt-4">{children}</div>
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  );
}
