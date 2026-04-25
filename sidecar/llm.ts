import Groq from "groq-sdk";

const SYSTEM_PROMPT =
  "You are a chill, helpful assistant for a personal autonomous trading bot. " +
  "Your owner texts you casually to check in on their bot's activity.\n\n" +
  "Tone rules:\n" +
  "- Always write in all lowercase, except: ticker symbols (AAPL, NVDA, SPY), " +
  "acronyms (PnL, RSI, MACD, ATR, EMA), dollar amounts ($99,996), " +
  "and percentages when part of a metric\n" +
  "- Be conversational and natural — like texting a knowledgeable friend, " +
  "not reading a report\n" +
  "- Match the energy of the message: casual greeting = casual reply, " +
  "specific question = specific answer\n" +
  "- If someone says 'thanks', 'ok', 'cool', 'hey' or any casual non-question, " +
  "respond naturally like a person would — 'of course!', 'anytime!', " +
  "'lmk if you need anything else' etc. Never say there is no question to answer.\n" +
  "- Keep responses short and punchy unless detail is genuinely needed\n" +
  "- Never start a response with 'I' as the first word\n" +
  "- Don't over-explain. If the answer is simple, keep it simple.\n" +
  "- If context is unavailable, say something like 'ugh, can't pull the data " +
  "rn — try again in a sec' not a formal error message";

const MODEL = "llama-3.3-70b-versatile";

let client: Groq | null = null;

function getClient(): Groq {
  if (!client) {
    const key = process.env.GROQ_API_KEY;
    if (!key) throw new Error("GROQ_API_KEY not set");
    client = new Groq({ apiKey: key });
  }
  return client;
}

export async function askGemini(userMessage: string, context: unknown): Promise<string> {
  try {
    const userTurn =
      `Bot context (JSON):\n${JSON.stringify(context, null, 2)}\n\n` +
      `User question:\n${userMessage}`;

    const completion = await getClient().chat.completions.create({
      model: MODEL,
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: userTurn },
      ],
    });

    return (completion.choices[0]?.message?.content ?? "").trim() ||
      "Sorry, I couldn't generate a response right now.";
  } catch (err) {
    console.error("askGemini failed:", err);
    return "Sorry, I couldn't generate a response right now.";
  }
}
