export interface InteractionStateResponse {
  target_type: "post" | "topic";
  target_id: string;
  active: boolean;
  count: number;
}

export interface VoteStateResponse {
  target_type: "post" | "topic";
  target_id: string;
  value: number;
  score: number;
  count: number;
}
