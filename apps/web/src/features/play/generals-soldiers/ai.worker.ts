import { chooseAiMove, type AiRequest, type AiResponse } from "./ai";

self.onmessage = (event: MessageEvent<AiRequest>) => {
  const { id, state, difficulty, recentPositions } = event.data;
  const result = chooseAiMove(state, difficulty, recentPositions);
  const response: AiResponse = { id, ...result };
  self.postMessage(response);
};
