
import { useState, type FormEvent } from "react";

import {
  Box,
  Button,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";

import {
  ArrowForward,
  Explore,
  FlightTakeoff,
  Hiking,
  Landscape,
  LocalDining,
  LocationOn,
  Museum,
  SelfImprovement,
  Speed,
  Pets,
  CalendarMonth,
} from "@mui/icons-material";

import type {
  TravelPreferences,
  Interest,
  Pace,
} from "../types/trip";

const interests = [
  { value: "adventure", label: "Adventure", icon: Hiking },
  { value: "nature", label: "Nature", icon: Landscape },
  { value: "culture", label: "Culture", icon: Museum },
  { value: "food", label: "Food", icon: LocalDining },
  { value: "wildlife", label: "Wildlife", icon: Pets },
  { value: "relaxation", label: "Relaxation", icon: SelfImprovement },
  { value: "other", label: "Other", icon: Explore },
] as const;

const paceOptions = [
  {
    value: "relaxed",
    label: "Relaxed",
    description: "Take it slow",
    icon: SelfImprovement,
  },
  {
    value: "balanced",
    label: "Balanced",
    description: "A bit of everything",
    icon: Explore,
  },
  {
    value: "active",
    label: "Active",
    description: "Pack the days",
    icon: Speed,
  },
] as const;

interface TravelFormProps {
  onSubmit: (preferences: TravelPreferences) => void;
  loading: boolean;
}

export default function TravelForm({
  onSubmit,
  loading,
}: TravelFormProps) {
  const [destination, setDestination] = useState("");
  const [durationDays, setDurationDays] = useState(5);
  const [selectedInterests, setSelectedInterests] = useState<Interest[]>([]);
  const [pace, setPace] = useState<Pace>("balanced");

  const toggleInterest = (interest: Interest) => {
    setSelectedInterests((current) =>
      current.includes(interest)
        ? current.filter((item) => item !== interest)
        : [...current, interest]
    );
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    onSubmit({
      destination: destination.trim(),
      duration_days: durationDays,
      interests: selectedInterests,
      pace,
    });
  };

  const isValid =
    destination.trim().length >= 2 &&
    Number.isInteger(durationDays) &&
    durationDays >= 1 &&
    durationDays <= 30 &&
    selectedInterests.length > 0;

  return (
    <Paper
      elevation={0}
      sx={{
        maxWidth: 760,
        mx: "auto",
        p: { xs: 3, sm: 5 },
        borderRadius: 4,
        border: "1px solid",
        borderColor: "divider",
        boxShadow: "0 12px 40px rgba(0,0,0,0.04)",
      }}
    >
      <Stack
        spacing={1}
        sx={{
          alignItems: "center",
          mb: 4,
        }}
      >
        <FlightTakeoff
          color="primary"
          sx={{ fontSize: 40, mb: 1 }}
        />

        <Typography
          variant="h4"
          sx={{
            fontWeight: 800,
            textAlign: "center",
          }}
        >
          Plan Your Next Adventure
        </Typography>

        <Typography
          color="text.secondary"
          sx={{ textAlign: "center" }}
        >
          Tell us where you want to go and what you love.
        </Typography>
      </Stack>

      <Box component="form" onSubmit={handleSubmit}>
        <Stack spacing={3}>
          <TextField
            label="Where do you want to go?"
            placeholder="e.g. Chiang Mai, Thailand"
            value={destination}
            onChange={(event) =>
              setDestination(event.target.value)
            }
            required
            fullWidth
            slotProps={{
              input: {
                startAdornment: (
                  <LocationOn
                    color="action"
                    sx={{ mr: 1 }}
                  />
                ),
              },
              htmlInput: { minLength: 2 },
            }}
          />

          <TextField
            label="How many days?"
            type="number"
            value={durationDays}
            onChange={(event) =>
              setDurationDays(Number(event.target.value))
            }
            required
            fullWidth
            slotProps={{
              input: {
                startAdornment: (
                  <CalendarMonth
                    color="action"
                    sx={{ mr: 1 }}
                  />
                ),
              },
              htmlInput: {
                min: 1,
                max: 30,
                step: 1,
              },
            }}
          />

          <Box>
            <Typography
              variant="h6"
              sx={{ fontWeight: 700, mb: 0.5 }}
            >
              What interests you?
            </Typography>

            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ mb: 2 }}
            >
              Select one or more experiences.
            </Typography>

            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: {
                  xs: "repeat(2, minmax(0, 1fr))",
                  sm: "repeat(3, minmax(0, 1fr))",
                },
                gap: 1.5,
              }}
            >
              {interests.map((interest) => {
                const selected = selectedInterests.includes(
                  interest.value
                );
                const Icon = interest.icon;

                return (
                  <Box
                    key={interest.value}
                    component="button"
                    type="button"
                    aria-pressed={selected}
                    onClick={() =>
                      toggleInterest(interest.value)
                    }
                    sx={{
                      cursor: "pointer",
                      font: "inherit",
                      minHeight: 95,
                      p: 2,
                      borderRadius: 3,
                      border: "2px solid",
                      borderColor: selected
                        ? "primary.main"
                        : "divider",
                      bgcolor: selected
                        ? "primary.50"
                        : "background.paper",
                      color: selected
                        ? "primary.main"
                        : "text.primary",
                      transition: "all 0.2s ease",
                      "&:hover": {
                        borderColor: "primary.main",
                        transform: "translateY(-2px)",
                      },
                    }}
                  >
                    <Stack
                      spacing={1}
                      sx={{ alignItems: "center" }}
                    >
                      <Icon sx={{ fontSize: 27 }} />

                      <Typography
                        variant="body2"
                        sx={{ fontWeight: 600 }}
                      >
                        {interest.label}
                      </Typography>
                    </Stack>
                  </Box>
                );
              })}
            </Box>
          </Box>

          <Box>
            <Typography
              variant="h6"
              sx={{ fontWeight: 700, mb: 0.5 }}
            >
              What's your travel pace?
            </Typography>

            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ mb: 2 }}
            >
              Choose how busy your days should be.
            </Typography>

            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: {
                  xs: "1fr",
                  sm: "repeat(3, minmax(0, 1fr))",
                },
                gap: 1.5,
              }}
            >
              {paceOptions.map((option) => {
                const selected = pace === option.value;
                const Icon = option.icon;

                return (
                  <Box
                    key={option.value}
                    component="button"
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setPace(option.value)}
                    sx={{
                      cursor: "pointer",
                      font: "inherit",
                      textAlign: "center",
                      p: 2,
                      borderRadius: 3,
                      border: "2px solid",
                      borderColor: selected
                        ? "primary.main"
                        : "divider",
                      bgcolor: selected
                        ? "primary.50"
                        : "background.paper",
                      color: selected
                        ? "primary.main"
                        : "text.primary",
                      transition: "all 0.2s ease",
                      "&:hover": {
                        borderColor: "primary.main",
                      },
                    }}
                  >
                    <Stack
                      spacing={0.5}
                      sx={{ alignItems: "center" }}
                    >
                      <Icon sx={{ fontSize: 27, mb: 0.5 }} />

                      <Typography
                        variant="subtitle2"
                        sx={{ fontWeight: 700 }}
                      >
                        {option.label}
                      </Typography>

                      <Typography
                        variant="caption"
                        sx={{
                          color: selected
                            ? "primary.main"
                            : "text.secondary",
                        }}
                      >
                        {option.description}
                      </Typography>
                    </Stack>
                  </Box>
                );
              })}
            </Box>
          </Box>

          <Button
            type="submit"
            variant="contained"
            size="large"
            fullWidth
            disabled={!isValid || loading}
            endIcon={
              loading ? undefined : <ArrowForward />
            }
            sx={{
              py: 1.8,
              borderRadius: 3,
              fontSize: "1rem",
              fontWeight: 700,
              textTransform: "none",
              boxShadow: "none",
              "&:hover": {
                boxShadow: "0 6px 20px rgba(0,0,0,0.15)",
              },
            }}
          >
            {loading ? (
              <Stack
                direction="row"
                spacing={1.5}
                sx={{ alignItems: "center" }}
              >
                <CircularProgress
                  size={20}
                  color="inherit"
                />
                <span>Creating your trip...</span>
              </Stack>
            ) : (
              "Generate My Trip"
            )}
          </Button>
        </Stack>
      </Box>
    </Paper>
  );
}