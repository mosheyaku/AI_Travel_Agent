
import { useState, type FormEvent } from "react";
import type {
  TravelPreferences,
  Interest,
  Pace,
} from "../types/trip";

import {
  Box,
  Button,
  Checkbox,
  Chip,
  FormControl,
  FormControlLabel,
  FormGroup,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  TextField,
  Typography,
} from "@mui/material";

const interests = [
  { value: "adventure", label: "Adventure" },
  { value: "nature", label: "Nature" },
  { value: "culture", label: "Culture" },
  { value: "food", label: "Food" },
  { value: "wildlife", label: "Wildlife" },
  { value: "relaxation", label: "Relaxation" },
  { value: "other", label: "Other" },
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

    const preferences: TravelPreferences = {
      destination: destination.trim(),
      duration_days: durationDays,
      interests: selectedInterests,
      pace,
    };

    onSubmit(preferences);
  };

  return (
    <Paper
      elevation={2}
      sx={{
        p: { xs: 3, sm: 4 },
        maxWidth: 650,
        mx: "auto",
        borderRadius: 3,
      }}
    >
      <Typography variant="h4" sx={{ fontWeight: 700 }} gutterBottom>
        Plan Your Adventure
      </Typography>

      <Typography color="text.secondary" sx={{ mb: 4 }}>
        Tell us what you love, and we'll plan your trip.
      </Typography>

      <Box component="form" onSubmit={handleSubmit}>
        <TextField
          label="Destination"
          placeholder="e.g. Chiang Mai, Thailand"
          value={destination}
          onChange={(event) => setDestination(event.target.value)}
          required
          fullWidth
          margin="normal"
          slotProps={{
            htmlInput: { minLength: 2 },
          }}
        />

        <TextField
          label="Number of days"
          type="number"
          value={durationDays}
          onChange={(event) =>
            setDurationDays(Number(event.target.value))
          }
          required
          fullWidth
          margin="normal"
          slotProps={{
            htmlInput: { min: 1, max: 30, step: 1 },
          }}
        />

        <Typography variant="h6" sx={{ mt: 3, mb: 1 }}>
          Your Interests
        </Typography>

        <FormGroup>
          {interests.map((interest) => (
            <FormControlLabel
              key={interest.value}
              control={
                <Checkbox
                  checked={selectedInterests.includes(interest.value)}
                  onChange={() => toggleInterest(interest.value)}
                />
              }
              label={interest.label}
            />
          ))}
        </FormGroup>

        {selectedInterests.length > 0 && (
          <Box
            sx={{
              display: "flex",
              flexWrap: "wrap",
              gap: 1,
              mt: 1,
            }}
          >
            {selectedInterests.map((interest) => (
              <Chip
                key={interest}
                label={
                  interests.find(
                    (item) => item.value === interest
                  )?.label
                }
                onDelete={() => toggleInterest(interest)}
                color="primary"
                variant="outlined"
              />
            ))}
          </Box>
        )}

        <FormControl fullWidth sx={{ mt: 3 }}>
          <InputLabel id="pace-label">
            Travel Pace
          </InputLabel>

          <Select
            labelId="pace-label"
            value={pace}
            label="Travel Pace"
            onChange={(event) =>
              setPace(event.target.value as Pace)
            }
          >
            <MenuItem value="relaxed">Relaxed</MenuItem>
            <MenuItem value="balanced">Balanced</MenuItem>
            <MenuItem value="active">Active</MenuItem>
          </Select>
        </FormControl>

        <Button
          type="submit"
          variant="contained"
          size="large"
          fullWidth
          disabled={
            loading ||
            destination.trim().length < 2 ||
            !Number.isInteger(durationDays) ||
            durationDays < 1 ||
            durationDays > 30 ||
            selectedInterests.length === 0
          }
          sx={{ mt: 4, py: 1.5 }}
        >
          {loading ? "Generating Trip..." : "Generate My Trip"}
        </Button>
      </Box>
    </Paper>
  );
}