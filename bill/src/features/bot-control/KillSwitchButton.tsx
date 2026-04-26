import { useState } from "react";
import { OctagonAlert } from "lucide-react";
import { Button } from "@/components/Button";
import { Dialog } from "@/components/Dialog";

export function KillSwitchButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button variant="critical" size="md" onClick={() => setOpen(true)}>
        <OctagonAlert size={16} />
        Kill switch
      </Button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Trigger kill switch?"
        description="Cancels all open orders and liquidates every position. Bot will halt until tomorrow's open."
      >
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button variant="critical" onClick={() => setOpen(false)} disabled>
            Confirm halt
          </Button>
        </div>
      </Dialog>
    </>
  );
}
