import { BotStatusIndicator } from "@/features/bot-control/BotStatusIndicator";
import { RegimePill } from "@/features/bot-control/RegimePill";
import { KillSwitchButton } from "@/features/bot-control/KillSwitchButton";
import { AccountEquity } from "@/features/portfolio/AccountEquity";
import { BuyingPower } from "@/features/portfolio/BuyingPower";

export function TopNav() {
  return (
    <header
      className="fixed inset-x-0 top-0 z-40 flex items-center justify-between gap-6 border-b border-border bg-surface px-5"
      style={{ height: 56 }}
    >
      <div className="flex items-center gap-5">
        <span className="font-display italic" style={{ fontSize: 20 }}>
          Bill
        </span>
        <BotStatusIndicator />
        <RegimePill />
      </div>
      <div className="flex items-center gap-6">
        <BuyingPower />
        <AccountEquity />
        <KillSwitchButton />
      </div>
    </header>
  );
}
