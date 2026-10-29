
import type {
    GenerateTripResponse,
    TravelPreferences,
  } from "../types/trip";
  
  export async function generateTrip(
    preferences: TravelPreferences
  ): Promise<GenerateTripResponse> {
    const response = await fetch("/api/trips/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(preferences),
    });
  
    if (!response.ok) {
      throw new Error(
        `Failed to generate trip (HTTP ${response.status}).`
      );
    }
  
    return (await response.json()) as GenerateTripResponse;
  }  