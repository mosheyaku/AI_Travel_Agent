
export type Interest =
  | "adventure"
  | "nature"
  | "culture"
  | "food"
  | "wildlife"
  | "relaxation"
  | "other";

export type Pace = "relaxed" | "balanced" | "active";

export interface TravelPreferences {
  destination: string;
  duration_days: number;
  interests: Interest[];
  pace: Pace;
  budget?: number | null;
}

export interface ItineraryActivity {
  name: string;
  activity_type: string;
  description: string;
  source_indices: number[];
  location_status: string;
  latitude: number | null;
  longitude: number | null;
  google_place_id: string | null;
  duration_type: "short" | "half_day" | "full_day" | "unknown";
}

export interface ItineraryDay {
  day: number;
  activities: ItineraryActivity[];
  max_distance_km: number | null;
  driving_distance_km: number | null;
  driving_duration_minutes: number | null;
  driving_status: "verified" | "exceeds_limit" | "unknown";
  total_driving_distance_km: number | null;
  total_driving_duration_minutes: number | null;
}

export interface Trip {
  destination: string;
  days: ItineraryDay[];
}

export interface TripSource {
  title: string;
  url: string;
}

export interface GenerateTripResponse {
  trip: Trip;
  sources: TripSource[];
}