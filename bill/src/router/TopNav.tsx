import { BotStatusIndicator } from "@/features/bot-control/BotStatusIndicator";
import { RegimePill } from "@/features/bot-control/RegimePill";
import { KillSwitchButton } from "@/features/bot-control/KillSwitchButton";
import { AccountEquity } from "@/features/portfolio/AccountEquity";
import { BuyingPower } from "@/features/portfolio/BuyingPower";
import { Link } from "@tanstack/react-router";


export function TopNav() {
  return (
    <header
      className="fixed inset-x-0 top-0 z-50 flex items-center justify-between gap-6 border-b border-border bg-surface px-5"
      style={{ height: 56 }}
    >
      <div className="flex items-center gap-8">
        <Link to="/" className="font-display italic leading-none" style={{ fontSize: 22 }}>
          Bill
        </Link>
        <div className="flex items-center gap-6">
          <BotStatusIndicator />
          <RegimePill />
        </div>
      </div>
      <div className="flex items-center gap-6">
        <BuyingPower />
        <AccountEquity />
        <KillSwitchButton />
      </div>
    </header>
  );
}
