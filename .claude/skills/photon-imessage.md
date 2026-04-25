# Photon Spectrum iMessage Integration

## Package
spectrum-ts (TypeScript 5+), npm install spectrum-ts

## Auth (Cloud mode — correct for Linux server)
const app = await Spectrum({ projectId: process.env.PHOTON_PROJECT_ID, projectSecret: process.env.PHOTON_PROJECT_SECRET, providers: [imessage.config()] })

## Receive messages
for await (const [space, message] of app.messages) { ... }

## Send response
await space.send("text")

## Typing indicator
await space.responding(async () => { await space.send(result) })

## Proactive send (scheduled summary)
const im = imessage(app)
const user = await im.user("+1XXXXXXXXXX")
const dm = await im.space(user)
await dm.send("summary text")

## Filter own messages
if (message.sender.id === process.env.MY_PHONE_NUMBER) continue

## Content type guard
Only handle message.content.type === "text"

## Key constraints
- No webhook support yet — sidecar connects outbound
- Python SDK not available — must be Node.js/TypeScript sidecar
- local: true mode requires macOS — do not use on Linux droplet
- Gemini Flash 2.0 used for LLM (not Claude) via @google/generative-ai
- FastAPI on same droplet provides live bot context at http://localhost:8000
