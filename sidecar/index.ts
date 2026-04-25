import "dotenv/config";
import cron from "node-cron";
import { Spectrum } from "spectrum-ts";
import { imessage } from "spectrum-ts/providers/imessage";

import { fetchBotContext } from "./context.js";
import { askGemini } from "./llm.js";
import { buildDailySummary } from "./summary.js";

const REQUIRED_ENV = [
  "PHOTON_PROJECT_ID",
  "PHOTON_PROJECT_SECRET",
  "GROQ_API_KEY",
  "MY_PHONE_NUMBER",
  "PHOTON_IMESSAGE_NUMBER",
] as const;

function validateEnv(): void {
  const missing = REQUIRED_ENV.filter((k) => !process.env[k]?.trim());
  if (missing.length > 0) {
    throw new Error(`Missing required env vars: ${missing.join(", ")}`);
  }
}

async function main() {
  validateEnv();

  const app = await Spectrum({
    projectId: process.env.PHOTON_PROJECT_ID!,
    projectSecret: process.env.PHOTON_PROJECT_SECRET!,
    providers: [imessage.config()],
  });

  console.log("Sidecar connected to Photon Spectrum cloud.");

  const im = imessage(app);
  const myNumber = process.env.MY_PHONE_NUMBER!;
  const ownNumber = process.env.PHOTON_IMESSAGE_NUMBER!;

  // Daily summary: 4:30 PM ET, Mon-Fri
  cron.schedule(
    "30 16 * * 1-5",
    async () => {
      try {
        console.log("Running scheduled daily summary...");
        const context = await fetchBotContext();
        const summary = await buildDailySummary(context);
        const user = await im.user(myNumber);
        const dm = await im.space(user);
        await dm.send(summary);
        console.log("Daily summary sent.");
      } catch (err) {
        console.error("Daily summary job failed:", err);
      }
    },
    { timezone: "America/New_York" }
  );

  // Graceful shutdown
  const shutdown = async (signal: string) => {
    console.log(`Received ${signal}, shutting down...`);
    try {
      await app.stop();
    } catch (err) {
      console.error("Error during shutdown:", err);
    }
    process.exit(0);
  };
  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));

  // Message loop
  for await (const [space, message] of app.messages) {
    if (message.sender.id === ownNumber) continue;
    if (message.content.type !== "text") continue;

    const userText = message.content.text;
    console.log(`Received message from ${message.sender.id}: ${userText}`);

    await space.responding(async () => {
      const context = await fetchBotContext();
      const reply = await askGemini(userText, context);
      await space.send(reply);
    });
  }
}

main().catch((err) => {
  console.error("Sidecar fatal error:", err);
  process.exit(1);
});
