
import { useState } from "react";
import {
  Alert,
  Box,
  CircularProgress,
  Container,
  CssBaseline,
  Typography,
} from "@mui/material";

import TravelForm from "./components/TravelForm";
import ItineraryView from "./components/ItineraryView";
import { generateTrip } from "./api/trips";

import type {
  GenerateTripResponse,
  TravelPreferences,
} from "./types/trip";

export default function App() {
  const [tripData, setTripData] =
    useState<GenerateTripResponse | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerateTrip = async (
    preferences: TravelPreferences
  ) => {
    setLoading(true);
    setError(null);
    setTripData(null);

    try {
      const result = await generateTrip(preferences);
      setTripData(result);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An unexpected error occurred."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <CssBaseline />

      <Box
        sx={{
          minHeight: "100vh",
          bgcolor: "#f5f7fb",
          py: { xs: 4, md: 8 },
        }}
      >
        <Container maxWidth="md">
          <TravelForm
            onSubmit={handleGenerateTrip}
            loading={loading}
          />

          {loading && (
            <Box sx={{ textAlign: "center", mt: 4 }}>
              <CircularProgress />

              <Typography sx={{ mt: 2 }}>
                Creating your personalized itinerary...
              </Typography>
            </Box>
          )}

          {error && (
            <Alert severity="error" sx={{ mt: 3 }}>
              {error}
            </Alert>
          )}

          {tripData && <ItineraryView data={tripData} />}
        </Container>
      </Box>
    </>
  );
}