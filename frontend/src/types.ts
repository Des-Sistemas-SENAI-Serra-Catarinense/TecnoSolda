export type Mode = 'off' | 'raised' | 'lowered' | 'missing_glove' | 'hidden_glove' | 'occluded' | 'unavailable';
export interface Access { username: string; role: string; csrf: string; expires_in: number }
export interface Detection {
  label: string; confidence: number | null; xyxy: [number, number, number, number];
  assessment: 'confirmed' | 'irregular' | 'inconclusive'; simulated: boolean;
}
export interface AlertEvent {
  sequence: number; occurred_at: string; kind: string; state: string;
  reason: string; epi: string | null; origin: string; review: string; actor: string | null;
}
export interface LiveState {
  sequence: number | null;
  camera: { connected: boolean; source: 'real'; message: string; width: number; height: number };
  inference: { mode: Mode; simulated: boolean; available: boolean; analyzing: boolean; message: string };
  sensor: { simulated: boolean; removed: boolean };
  metrics: { fps: number; pipeline_ms: number | null; frame_age_ms: number | null };
  status: {
    state: string; reason: string; green: boolean; red: boolean;
    respirator_verified: boolean; initial_verified: boolean;
    helmet: string; apron: string; left_glove: string; right_glove: string;
  };
  simulated_outputs: { green: boolean; red: boolean; alarm: boolean };
  physical_outputs_connected: boolean;
  detections: Detection[]; events: AlertEvent[]; access_expires_in: number;
}
