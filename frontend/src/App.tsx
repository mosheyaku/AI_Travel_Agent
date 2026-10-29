
import { useEffect, useRef, useState } from "react";

import {
  Alert,
  Box,
  CircularProgress,
  Container,
  CssBaseline,
  Divider,
  Stack,
  ThemeProvider,
  Typography,
  createTheme,
} from "@mui/material";

import {
  AutoAwesome,
  ExploreOutlined,
} from "@mui/icons-material";

import TravelForm from "./components/TravelForm";
import ItineraryView from "./components/ItineraryView";
import { generateTrip } from "./api/trips";

import type {
  GenerateTripResponse,
  TravelPreferences,
} from "./types/trip";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#18796B",
      light: "#4CA899",
      dark: "#10594F",
      contrastText: "#FFFFFF",
    },
    secondary: {
      main: "#E89B50",
    },
    background: {
      default: "#F6F8F6",
      paper: "#FFFFFF",
    },
    text: {
      primary: "#19312D",
      secondary: "#64756F",
    },
    divider: "#E1E9E5",
  },
  typography: {
    fontFamily:
      '"Inter", "Segoe UI", Roboto, Arial, sans-serif',
    h4: {
      fontWeight: 800,
      letterSpacing: "-0.035em",
    },
    h6: {
      fontWeight: 700,
    },
    button: {
      textTransform: "none",
      fontWeight: 700,
    },
  },
  shape: {
    borderRadius: 12,
  },
});

function getErrorMessage(error: unknown): string {
  if (error instanceof TypeError) {
    return "Unable to connect to the server. Please try again.";
  }

  if (error instanceof Error) {
    if (error.message.includes("502")) {
      return "We couldn't generate a verified itinerary for this destination. Try another destination or different interests.";
    }

    return error.message;
  }

  return "Something went wrong. Please try again.";
}

export default function App() {
  const [tripData, setTripData] =
    useState<GenerateTripResponse | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resultRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (tripData || error) {
      resultRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  }, [tripData, error]);

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
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />

      <Box
        sx={{
          minHeight: "100vh",
          bgcolor: "background.default",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <Box
          component="header"
          sx={{
            bgcolor: "background.paper",
            borderBottom: "1px solid",
            borderColor: "divider",
          }}
        >
          <Container maxWidth="lg">
            <Stack
              direction="row"
              spacing={1.5}
              sx={{ alignItems: "center", py: 2 }}
            >
              <Box
                sx={{
                  width: 42,
                  height: 42,
                  borderRadius: 2.5,
                  bgcolor: "primary.main",
                  color: "primary.contrastText",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <ExploreOutlined sx={{ fontSize: 27 }} />
              </Box>

              <Box>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 800,
                    lineHeight: 1.2,
                    letterSpacing: "-0.03em",
                  }}
                >
                  Travel Architect
                </Typography>

                <Typography
                  variant="caption"
                  color="text.secondary"
                >
                  Your AI travel planner
                </Typography>
              </Box>
            </Stack>
          </Container>
        </Box>

        <Box
          component="main"
          sx={{
            flex: 1,
            py: { xs: 4, md: 7 },
            background:
              "radial-gradient(ellipse at 50% 0%, #E4F2EC 0%, #F6F8F6 55%)",
          }}
        >
          <Container maxWidth="md">
            <Stack
              direction="row"
              spacing={1}
              sx={{
                alignItems: "center",
                justifyContent: "center",
                mb: 3,
              }}
            >
              <AutoAwesome
                sx={{ fontSize: 17, color: "primary.main" }}
              />

              <Typography
                variant="overline"
                sx={{
                  color: "primary.dark",
                  fontWeight: 700,
                  letterSpacing: 1.5,
                }}
              >
                Explore more. Plan less.
              </Typography>
            </Stack>

            <TravelForm
              onSubmit={handleGenerateTrip}
              loading={loading}
            />

            <Box ref={resultRef} sx={{ scrollMarginTop: 24 }}>
              {loading && (
                <Stack
                  spacing={2}
                  sx={{
                    alignItems: "center",
                    textAlign: "center",
                    mt: 5,
                    py: 4,
                  }}
                >
                  <CircularProgress size={40} />

                  <Typography sx={{ fontWeight: 700 }}>
                    Creating your personalized itinerary...
                  </Typography>

                  <Typography
                    variant="body2"
                    color="text.secondary"
                  >
                    Searching for attractions and planning your route.
                    This may take a little while.
                  </Typography>
                </Stack>
              )}

              {error && (
                <Alert
                  severity="error"
                  sx={{ mt: 3, borderRadius: 2 }}
                >
                  {error}
                </Alert>
              )}

              {tripData && <ItineraryView data={tripData} />}
            </Box>
          </Container>
        </Box>

        <Box
          component="footer"
          sx={{ bgcolor: "background.paper" }}
        >
          <Divider />

          <Container maxWidth="lg">
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{
                display: "block",
                textAlign: "center",
                py: 3,
              }}
            >
              Travel Architect — Discover experiences worth traveling for.
            </Typography>
          </Container>
        </Box>
      </Box>
    </ThemeProvider>
  );
}