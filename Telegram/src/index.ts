import { createBot } from "./bot.js";

const bot = createBot();

bot.start({
  onStart: () => console.log(JSON.stringify({ event: "bot_started" })),
});
